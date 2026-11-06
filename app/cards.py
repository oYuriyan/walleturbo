"""Faturas: despesas por mês de vencimento; pagamentos afetam somente o caixa."""

import calendar
import hashlib
import json
from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import Account, Card, Statement, Charge, StatementPayment, db_session
from app.domain import CATEGORIES, parse_csv, import_keys
from app.security import current_user
from app.receipts import claim
from app.db import RequestReceipt, Transaction
from app.import_marks import reserve, remove as remove_import, result as import_result
from app.import_review import candidates

router = APIRouter(prefix="/api")
MONTH_PATTERN = r"^(19\d{2}|[2-9]\d{3})-(0[1-9]|1[0-2])$"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AccountInput(Input):
    name: str = Field(min_length=1, max_length=80)


class CardInput(AccountInput):
    due_day: int = Field(strict=True, ge=1, le=31)


class PurchaseInput(Input):
    request_id: UUID
    card_id: str = Field(min_length=1, max_length=36)
    first_month: str = Field(pattern=MONTH_PATTERN)
    date: date
    description: str = Field(min_length=1, max_length=160)
    amount_cents: int = Field(strict=True, gt=0, le=99999999999)
    installments: int = Field(default=1, strict=True, ge=1, le=36)
    kind: Literal["expense", "refund"] = "expense"
    category: str = "Outros"
    reviewed: bool = False

    @field_validator("category")
    @classmethod
    def valid_category(cls, value):
        if value not in CATEGORIES or value == "Renda":
            raise ValueError("Categoria de despesa inválida")
        return value

    @model_validator(mode="after")
    def valid_installments(self):
        if self.amount_cents < self.installments:
            raise ValueError("Cada parcela deve ter pelo menos um centavo")
        if self.kind == "refund" and self.installments != 1:
            raise ValueError(
                "Estorno deve ser registrado na fatura em que foi creditado"
            )
        shift_month(self.first_month, self.installments - 1)
        return self


class ReviewInput(Input):
    expected_version: int = Field(strict=True, ge=1, le=2147483646)
    category: str
    reviewed: bool

    @field_validator("category")
    @classmethod
    def valid_category(cls, value):
        return PurchaseInput.valid_category(value)


class ReconcileInput(Input):
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_cents: int = Field(strict=True, ge=0, le=99999999999)


class PaymentInput(Input):
    request_id: UUID
    account_id: str = Field(min_length=1, max_length=36)
    date: date
    amount_cents: int = Field(strict=True, gt=0, le=99999999999)


class CardCSV(Input):
    content: str = Field(max_length=256000)


def shift_month(month, offset):
    year, m = map(int, month.split("-"))
    index = year * 12 + m - 1 + offset
    year, m = divmod(index, 12)
    if not 1900 <= year <= 9999:
        raise ValueError("Período fora do intervalo suportado")
    return f"{year:04d}-{m+1:02d}"


def due_date(month, day):
    year, m = map(int, month.split("-"))
    return date(year, m, min(day, calendar.monthrange(year, m)[1]))


def split_cents(total, count):
    amount, remainder = divmod(total, count)
    return [amount + (i < remainder) for i in range(count)]


def public(row):
    fields = {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in {"owner", "payload_hash", "import_key", "source_key"}
    }
    if isinstance(row, (Charge, Transaction)):
        fields["imported"] = row.import_key is not None
    return fields


def operation_revision(charges):
    return hashlib.sha256(
        json.dumps(
            [public(c) for c in sorted(charges, key=lambda c: c.installment)],
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()


def fingerprint(body):
    return hashlib.sha256(body.model_dump_json().encode()).hexdigest()


def owned(db, model, user, identifier, lock=False):
    query = select(model).where(model.id == identifier, model.owner == user)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if not row:
        raise HTTPException(404, "Registro não encontrado")
    return row


def require_active(row):
    if row.archived:
        raise HTTPException(
            409, "Cadastro arquivado. Reative antes de registrar uma nova operação."
        )
    return row


def active_statement_card(db, user, statement):
    return require_active(owned(db, Card, user, statement.card_id, lock=True))


def statement_for(db, user, card, month):
    # Chamador mantém lock no cartão: criação concorrente é serializada.
    statement = db.scalar(
        select(Statement).where(
            Statement.owner == user,
            Statement.card_id == card.id,
            Statement.month == month,
        )
    )
    if not statement:
        require_active(card)
        statement = Statement(
            owner=user,
            card_id=card.id,
            month=month,
            due_date=due_date(month, card.due_day),
            status="open",
        )
        db.add(statement)
        db.flush()
    return statement


def lock_statement(db, user, identifier):
    statement = owned(db, Statement, user, identifier)
    # Todos os escritores bloqueiam na mesma ordem: cartão, depois fatura.
    owned(db, Card, user, statement.card_id, lock=True)
    db.refresh(statement, with_for_update=True)
    return statement


def require_open(statement):
    if statement.status != "open":
        raise HTTPException(
            409, "Fatura conferida: reabra antes de alterar os lançamentos"
        )


def statement_totals(db, user, statement):
    charges = list(
        db.scalars(
            select(Charge)
            .where(Charge.owner == user, Charge.statement_id == statement.id)
            .order_by(Charge.date, Charge.id)
        )
    )
    payments = list(
        db.scalars(
            select(StatementPayment)
            .where(
                StatementPayment.owner == user,
                StatementPayment.statement_id == statement.id,
            )
            .order_by(StatementPayment.date, StatementPayment.id)
        )
    )
    total = sum(c.amount_cents * (-1 if c.kind == "refund" else 1) for c in charges)
    paid = sum(p.amount_cents for p in payments)
    snapshot = {
        **public(statement),
        "total_cents": total,
        "paid_cents": paid,
        "remaining_cents": total - paid,
        "pending": sum(not c.reviewed for c in charges),
        "charges": [public(c) for c in charges],
        "payments": [public(p) for p in payments],
    }
    snapshot["revision"] = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, default=str).encode()
    ).hexdigest()
    return snapshot


def require_statement_revision(snapshot, expected):
    if snapshot["revision"] != expected:
        raise HTTPException(
            409,
            "Fatura alterada em outra sessão. Atualize os dados e confira novamente.",
        )


@router.get("/accounts")
def accounts(user=Depends(current_user), db: Session = Depends(db_session)):
    return [
        public(a)
        for a in db.scalars(
            select(Account).where(Account.owner == user).order_by(Account.name)
        )
    ]


@router.post("/accounts", status_code=201)
def create_account(
    body: AccountInput, user=Depends(current_user), db: Session = Depends(db_session)
):
    account = Account(owner=user, **body.model_dump())
    db.add(account)
    db.commit()
    return public(account)


@router.get("/cards")
def cards(user=Depends(current_user), db: Session = Depends(db_session)):
    return [
        public(c)
        for c in db.scalars(select(Card).where(Card.owner == user).order_by(Card.name))
    ]


@router.post("/cards", status_code=201)
def create_card(
    body: CardInput, user=Depends(current_user), db: Session = Depends(db_session)
):
    card = Card(owner=user, **body.model_dump())
    db.add(card)
    db.commit()
    return public(card)


@router.get("/statements")
def statements(
    month: str = Query(pattern=MONTH_PATTERN),
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    return [
        statement_totals(db, user, s)
        for s in db.scalars(
            select(Statement)
            .where(Statement.owner == user, Statement.month == month)
            .order_by(Statement.due_date, Statement.id)
        )
    ]


@router.post("/cards/{card_id}/statements", status_code=201)
def create_statement(
    card_id: str,
    month: str = Query(pattern=MONTH_PATTERN),
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    try:
        shift_month(month, 0)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    card = owned(db, Card, user, card_id, lock=True)
    statement = statement_for(db, user, card, month)
    db.commit()
    return statement_totals(db, user, statement)


@router.post("/card-purchases", status_code=201)
def purchase(
    body: PurchaseInput, user=Depends(current_user), db: Session = Depends(db_session)
):
    owned(db, Card, user, body.card_id)
    receipt = claim(db, user, "purchase", body.request_id, fingerprint(body))
    card = owned(db, Card, user, body.card_id, lock=True)
    previous = list(
        db.scalars(
            select(Charge)
            .where(Charge.owner == user, Charge.operation_id == str(body.request_id))
            .order_by(Charge.installment)
        )
    )
    digest = fingerprint(body)
    if previous:
        if previous[0].payload_hash != digest:
            raise HTTPException(409, "Identificador de envio já usado com outros dados")
        return [public(c) for c in previous]
    if receipt.resource_id:
        raise HTTPException(
            409, "Operação não está mais disponível. Atualize os dados."
        )
    require_active(card)
    result = []
    for i, amount in enumerate(split_cents(body.amount_cents, body.installments)):
        statement = statement_for(db, user, card, shift_month(body.first_month, i))
        require_open(statement)
        charge = Charge(
            owner=user,
            statement_id=statement.id,
            date=body.date,
            description=body.description,
            amount_cents=amount,
            kind=body.kind,
            category=body.category,
            reviewed=body.reviewed,
            operation_id=str(body.request_id),
            payload_hash=digest,
            installment=i + 1,
            installments=body.installments,
        )
        db.add(charge)
        result.append(charge)
    receipt.resource_id = str(body.request_id)
    db.commit()
    return [public(c) for c in result]


@router.put("/card-charges/{charge_id}/review")
def review(
    charge_id: str,
    body: ReviewInput,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    charge = owned(db, Charge, user, charge_id)
    lock_statement(db, user, charge.statement_id)
    charge = owned(db, Charge, user, charge_id, lock=True)
    require_open(lock_statement(db, user, charge.statement_id))
    if charge.version != body.expected_version:
        raise HTTPException(
            409,
            "Lançamento de cartão alterado em outra sessão. Recarregue antes de revisar.",
        )
    charge.category, charge.reviewed = body.category, body.reviewed
    db.commit()
    return public(charge)


@router.delete("/card-operations/{operation_id}", status_code=204)
def delete_operation(
    operation_id: UUID,
    expected_revision: str = Query(pattern=r"^[a-f0-9]{64}$"),
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    charges = list(
        db.scalars(
            select(Charge).where(
                Charge.owner == user, Charge.operation_id == str(operation_id)
            )
        )
    )
    if not charges:
        cancelled = db.get(RequestReceipt, (user, "purchase", str(operation_id)))
        if cancelled and cancelled.cancelled:
            return
        raise HTTPException(404, "Compra não encontrada")
    receipt = claim(db, user, "purchase", operation_id, charges[0].payload_hash)
    card_ids = set(
        db.scalars(
            select(Statement.card_id).where(
                Statement.owner == user,
                Statement.id.in_([c.statement_id for c in charges]),
            )
        )
    )
    for card_id in sorted(card_ids):
        owned(db, Card, user, card_id, lock=True)
    charges = list(
        db.scalars(
            select(Charge)
            .where(Charge.owner == user, Charge.operation_id == str(operation_id))
            .execution_options(populate_existing=True)
        )
    )
    if operation_revision(charges) != expected_revision:
        raise HTTPException(
            409, "Compra alterada em outra sessão. Atualize antes de excluir."
        )
    for statement_id in sorted({c.statement_id for c in charges}):
        require_open(lock_statement(db, user, statement_id))
    for charge in charges:
        if charge.import_key:
            remove_import(
                db, user, "card", charge.statement_id, charge.import_key, charge.id
            )
        db.delete(charge)
    receipt.cancelled, receipt.resource_id = True, str(operation_id)
    db.commit()


@router.get("/statements/{statement_id}")
def get_statement(
    statement_id: str, user=Depends(current_user), db: Session = Depends(db_session)
):
    statement = lock_statement(db, user, statement_id)
    return statement_totals(db, user, statement)


@router.post("/statements/{statement_id}/close")
def close_statement(
    statement_id: str,
    body: ReconcileInput,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    statement = lock_statement(db, user, statement_id)
    require_open(statement)
    totals = statement_totals(db, user, statement)
    require_statement_revision(totals, body.expected_revision)
    if totals["pending"]:
        raise HTTPException(
            409, "Revise todas as categorias antes de conferir a fatura"
        )
    if totals["total_cents"] != body.expected_cents:
        raise HTTPException(
            409,
            "Total informado diverge dos lançamentos; confira compras, estornos e encargos",
        )
    statement.expected_cents = body.expected_cents
    statement.status = "closed"
    db.commit()
    return statement_totals(db, user, statement)


@router.post("/statements/{statement_id}/reopen")
def reopen(
    statement_id: str,
    expected_revision: str = Query(pattern=r"^[a-f0-9]{64}$"),
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    statement = lock_statement(db, user, statement_id)
    require_statement_revision(statement_totals(db, user, statement), expected_revision)
    if db.scalar(
        select(StatementPayment.id)
        .where(
            StatementPayment.owner == user,
            StatementPayment.statement_id == statement.id,
        )
        .limit(1)
    ):
        raise HTTPException(409, "Estorne os registros de pagamento antes de reabrir")
    statement.status, statement.expected_cents = "open", None
    db.commit()
    return statement_totals(db, user, statement)


@router.post("/statements/{statement_id}/payments", status_code=201)
def pay(
    statement_id: str,
    body: PaymentInput,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    owned(db, Statement, user, statement_id)
    owned(db, Account, user, body.account_id)
    digest = hashlib.sha256((statement_id + fingerprint(body)).encode()).hexdigest()
    receipt = claim(db, user, "payment", body.request_id, digest)
    statement = lock_statement(db, user, statement_id)
    account = owned(db, Account, user, body.account_id, lock=True)
    previous = db.scalar(
        select(StatementPayment).where(
            StatementPayment.owner == user,
            StatementPayment.request_id == str(body.request_id),
        )
    )
    if previous:
        if previous.payload_hash != digest:
            raise HTTPException(409, "Identificador de envio já usado com outros dados")
        return public(previous)
    if receipt.resource_id:
        raise HTTPException(
            409, "Pagamento não está mais disponível. Atualize os dados."
        )
    require_active(account)
    if statement.status != "closed":
        raise HTTPException(
            409, "Confira o total da fatura antes de registrar o pagamento"
        )
    if body.amount_cents > statement_totals(db, user, statement)["remaining_cents"]:
        raise HTTPException(409, "Pagamento excede o valor restante da fatura")
    payment = StatementPayment(
        owner=user,
        statement_id=statement.id,
        payload_hash=digest,
        **body.model_dump(exclude={"request_id"}),
        request_id=str(body.request_id),
    )
    db.add(payment)
    db.flush()
    receipt.resource_id = payment.id
    db.commit()
    return public(payment)


@router.delete("/statement-payments/{payment_id}", status_code=204)
def reverse_payment(
    payment_id: str,
    expected_version: int = Query(ge=1, le=2147483646),
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    payment = db.scalar(
        select(StatementPayment).where(
            StatementPayment.owner == user, StatementPayment.id == payment_id
        )
    )
    if payment is None:
        if db.scalar(
            select(RequestReceipt).where(
                RequestReceipt.owner == user,
                RequestReceipt.scope == "payment",
                RequestReceipt.resource_id == payment_id,
                RequestReceipt.cancelled.is_(True),
            )
        ):
            return
        raise HTTPException(404, "Registro não encontrado")
    receipt = claim(db, user, "payment", payment.request_id, payment.payload_hash)
    lock_statement(db, user, payment.statement_id)
    payment = owned(db, StatementPayment, user, payment_id, lock=True)
    if payment.version != expected_version:
        raise HTTPException(
            409, "Pagamento alterado em outra sessão. Atualize antes de remover."
        )
    db.delete(payment)
    receipt.cancelled = True
    db.commit()


def csv_entries(body):
    try:
        entries = parse_csv(body.content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if any(e.kind != "expense" for e in entries):
        raise HTTPException(
            422, "CSV de fatura aceita apenas despesas; registre estornos separadamente"
        )
    return entries


@router.post("/statements/{statement_id}/import/preview")
def preview(
    statement_id: str,
    body: CardCSV,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    statement = owned(db, Statement, user, statement_id)
    require_open(statement)
    active_statement_card(db, user, statement)
    entries = csv_entries(body)
    return {
        "entries": [e.model_dump() for e in entries],
        "possible_duplicates": candidates(
            db, Charge, user, entries, Charge.statement_id == statement.id
        ),
    }


@router.post("/statements/{statement_id}/import/confirm")
def import_statement(
    statement_id: str,
    body: CardCSV,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    statement = lock_statement(db, user, statement_id)
    require_open(statement)
    active_statement_card(db, user, statement)
    entries = csv_entries(body)
    keys = import_keys(entries)
    marks = reserve(db, user, "card", statement.id, keys)
    created = removed = 0
    for entry, key in zip(entries, keys):
        mark = marks[key]
        if mark.removed:
            removed += 1
            continue
        if mark.resource_id:
            if not db.scalar(
                select(Charge.id).where(
                    Charge.owner == user, Charge.id == mark.resource_id
                )
            ):
                mark.removed = True
                removed += 1
            continue
        row = Charge(
            owner=user,
            statement_id=statement.id,
            import_key=key,
            operation_id=str(uuid4()),
            payload_hash=key,
            installment=1,
            installments=1,
            **entry.model_dump(exclude={"account_id"}),
        )
        db.add(row)
        db.flush()
        mark.resource_id = row.id
        created += 1
    db.commit()
    return import_result(len(entries), created, removed)


def monthly_card_summary(db, user, month):
    charges = list(
        db.scalars(
            select(Charge)
            .join(
                Statement,
                (Charge.statement_id == Statement.id)
                & (Charge.owner == Statement.owner),
            )
            .where(Charge.owner == user, Statement.month == month)
        )
    )
    start = date.fromisoformat(month + "-01")
    end = date.fromisoformat(shift_month(month, 1) + "-01")
    paid = db.scalar(
        select(func.coalesce(func.sum(StatementPayment.amount_cents), 0)).where(
            StatementPayment.owner == user,
            StatementPayment.date >= start,
            StatementPayment.date < end,
        )
    )
    categories = {}
    for charge in charges:
        categories[charge.category] = categories.get(
            charge.category, 0
        ) + charge.amount_cents * (-1 if charge.kind == "refund" else 1)
    return {
        "card_expense_cents": sum(categories.values()),
        "card_payment_cents": paid,
        "card_categories": categories,
        "card_pending": sum(not c.reviewed for c in charges),
    }
