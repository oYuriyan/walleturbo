"""Planejamento determinístico com evidências e dados incompletos explícitos."""

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from app.cards import ReviewInput, shift_month, public
from app.db import (
    Transaction,
    Charge,
    Statement,
    StatementPayment,
    Goal,
    MonthPlan,
    Budget,
    db_session,
)
from app.security import current_user

router = APIRouter(prefix="/api/planning")
MONTH = r"^(19\d{2}|[2-9]\d{3})-(0[1-9]|1[0-2])$"


class PlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    income_reference_cents: int | None = Field(
        default=None, strict=True, gt=0, le=99999999999
    )
    buffer_cents: int = Field(default=0, strict=True, ge=0, le=99999999999)
    records_complete: bool = Field(default=False, strict=True)


class PlanEdit(PlanInput):
    expected_records_revision: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )

    @model_validator(mode="after")
    def reviewed_snapshot(self):
        if self.records_complete and self.expected_records_revision is None:
            raise ValueError(
                "Recarregue os registros antes de confirmar sua completude"
            )
        return self

    expected_version: int = Field(strict=True, ge=0, le=2147483646)


class BudgetInput(BaseModel):
    expected_version: int = Field(strict=True, ge=0, le=2147483646)
    model_config = ConfigDict(extra="forbid")
    category: str
    amount_cents: int = Field(strict=True, gt=0, le=99999999999)

    @field_validator("category")
    @classmethod
    def category_valid(cls, value):
        return ReviewInput.valid_category(value)


def period(month):
    try:
        start = date.fromisoformat(month + "-01")
        if not 1900 <= start.year <= 9998:
            raise ValueError()
        return start, date.fromisoformat(shift_month(month, 1) + "-01")
    except ValueError:
        raise HTTPException(422, "Mês fora do intervalo suportado") from None


def monthly_figures(db, user, month):
    start, end = period(month)
    rows = db.execute(
        select(
            Transaction.kind, Transaction.category, func.sum(Transaction.amount_cents)
        )
        .where(
            Transaction.owner == user, Transaction.date >= start, Transaction.date < end
        )
        .group_by(Transaction.kind, Transaction.category)
    ).all()
    income, categories = 0, defaultdict(int)
    for kind, category, amount in rows:
        amount = int(amount)
        if kind == "income":
            income += amount
        else:
            categories[category] += amount
    card_rows = db.execute(
        select(Charge.kind, Charge.category, func.sum(Charge.amount_cents))
        .join(
            Statement,
            (Charge.statement_id == Statement.id) & (Charge.owner == Statement.owner),
        )
        .where(Charge.owner == user, Statement.month == month)
        .group_by(Charge.kind, Charge.category)
    ).all()
    card_expense = 0
    for kind, category, amount in card_rows:
        amount = int(amount)
        signed = amount * (-1 if kind == "refund" else 1)
        categories[category] += signed
        card_expense += signed
    paid = db.scalar(
        select(func.coalesce(func.sum(StatementPayment.amount_cents), 0)).where(
            StatementPayment.owner == user,
            StatementPayment.date >= start,
            StatementPayment.date < end,
        )
    )
    paid = int(paid)
    pending = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.owner == user,
            Transaction.date >= start,
            Transaction.date < end,
            Transaction.reviewed.is_(False),
        )
    )
    pending += db.scalar(
        select(func.count())
        .select_from(Charge)
        .join(
            Statement,
            (Charge.statement_id == Statement.id) & (Charge.owner == Statement.owner),
        )
        .where(
            Charge.owner == user, Statement.month == month, Charge.reviewed.is_(False)
        )
    )
    count = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.owner == user, Transaction.date >= start, Transaction.date < end
        )
    )
    count += db.scalar(
        select(func.count())
        .select_from(Charge)
        .join(
            Statement,
            (Charge.statement_id == Statement.id) & (Charge.owner == Statement.owner),
        )
        .where(Charge.owner == user, Statement.month == month)
    )
    count += db.scalar(
        select(func.count())
        .select_from(StatementPayment)
        .where(
            StatementPayment.owner == user,
            StatementPayment.date >= start,
            StatementPayment.date < end,
        )
    )
    expense = sum(categories.values())
    return {
        "income_cents": income,
        "expense_cents": expense,
        "result_cents": income - expense,
        "cash_change_cents": income - expense + card_expense - paid,
        "categories": dict(categories),
        "pending": pending,
        "records_count": count,
    }


def normalize(description):
    return re.sub(
        r"\s+", " ", unicodedata.normalize("NFKC", description).casefold()
    ).strip()


def recurrence(db, user, month):
    start, _ = period(month)
    first = (
        shift_month(month, -5) if start.year > 1900 or start.month > 5 else "1900-01"
    )
    _, end = period(month)
    direct = list(
        db.execute(
            select(
                Transaction.id,
                Transaction.description,
                Transaction.date,
                Transaction.amount_cents,
            )
            .where(
                Transaction.owner == user,
                Transaction.category == "Assinaturas",
                Transaction.kind == "expense",
                Transaction.reviewed.is_(True),
                Transaction.date >= date.fromisoformat(first + "-01"),
                Transaction.date < end,
            )
            .order_by(Transaction.date, Transaction.id)
            .limit(1001)
        ).all()
    )
    card = list(
        db.execute(
            select(Charge.id, Charge.description, Statement.month, Charge.amount_cents)
            .join(
                Statement,
                (Charge.statement_id == Statement.id)
                & (Charge.owner == Statement.owner),
            )
            .where(
                Charge.owner == user,
                Charge.category == "Assinaturas",
                Charge.kind == "expense",
                Charge.reviewed.is_(True),
                Charge.installments == 1,
                Statement.month >= first,
                Statement.month <= month,
            )
            .order_by(Statement.month, Charge.id)
            .limit(1001)
        ).all()
    )
    if len(direct) + len(card) > 1000:
        return [], [
            "Recorrências não analisadas: mais de mil registros de assinatura na janela de seis meses."
        ]
    groups = defaultdict(list)
    for source, rows in (("transaction", direct), ("card_charge", card)):
        for identifier, description, when, amount in rows:
            groups[normalize(description)].append(
                {
                    "source": source,
                    "id": identifier,
                    "month": str(when)[:7],
                    "amount_cents": amount,
                    "description": description,
                }
            )
    result = []
    for name, evidence in sorted(groups.items()):
        months = sorted({e["month"] for e in evidence})
        if len(months) < 3 or month not in months:
            continue
        result.append(
            {
                "merchant": evidence[-1]["description"],
                "months": months,
                "total_cents": sum(e["amount_cents"] for e in evidence),
                "current_cents": sum(
                    e["amount_cents"] for e in evidence if e["month"] == month
                ),
                "evidence": evidence,
                "reason": "Descrição igual na categoria Assinaturas em pelo menos três meses. Confira utilidade e cobranças; economia não foi estimada.",
            }
        )
    return result, []


def goal_plan(goals, capacity, reference):
    remaining_capacity = capacity or 0
    output = []
    for goal in sorted(goals, key=lambda g: (g.deadline, g.id)):
        remaining = goal.target_cents - goal.saved_cents
        expired = goal.deadline < reference and remaining > 0
        months = max(
            1,
            (goal.deadline.year - reference.year) * 12
            + goal.deadline.month
            - reference.month
            + 1,
        )
        required = 0 if remaining <= 0 else (remaining + months - 1) // months
        suggestion = (
            None
            if capacity is None
            else (0 if expired else min(required, remaining_capacity))
        )
        if suggestion is not None:
            remaining_capacity -= suggestion
        output.append(
            {
                "id": goal.id,
                "name": goal.name,
                "deadline": goal.deadline,
                "remaining_cents": remaining,
                "required_monthly_cents": required,
                "suggested_cents": suggestion,
                "expired": expired,
                "gap_cents": (
                    None if suggestion is None else max(0, required - suggestion)
                ),
            }
        )
    return output


def signature(figures):
    return hashlib.sha256(json.dumps(figures, sort_keys=True).encode()).hexdigest()


@router.get("/{month}")
def report(month: str, user=Depends(current_user), db: Session = Depends(db_session)):
    with consistent_view(db):
        start, end = period(month)
        if not re.fullmatch(MONTH, month):
            raise HTTPException(422, "Mês inválido")
        figures = monthly_figures(db, user, month)
        records_revision = financial_revision(db, user, month)
        plan = db.get(MonthPlan, (user, month))
        config = (
            {key: getattr(plan, key) for key in PlanInput.model_fields}
            if plan
            else PlanInput().model_dump()
        )
        warnings = []
        if config["records_complete"] and plan.stats_signature != records_revision:
            config["records_complete"] = False
            warnings.append(
                "Os registros do mês mudaram após a confirmação. Confira os registros novamente."
            )
        if not config["records_complete"]:
            warnings.append(
                "Confirme a completude dos registros do mês para simular aportes."
            )
        if figures["pending"]:
            warnings.append("Revise as categorias pendentes antes de simular aportes.")
        if figures["income_cents"] <= 0:
            warnings.append(
                "Não há receita positiva registrada no mês; renda de referência sozinha não autoriza sugestão de aporte."
            )
        reference_income = (
            config["income_reference_cents"]
            if config["income_reference_cents"] is not None
            else figures["income_cents"]
        )
        # Nunca sugerir mais que o resultado registrado, o caixa registrado ou o cenário informado.
        capacity = (
            None
            if warnings
            else max(
                0,
                min(
                    figures["result_cents"],
                    figures["cash_change_cents"],
                    reference_income - figures["expense_cents"],
                )
                - config["buffer_cents"],
            )
        )
        budgets = []
        for budget in db.scalars(
            select(Budget)
            .where(Budget.owner == user, Budget.month == month)
            .order_by(Budget.category)
        ):
            spent = figures["categories"].get(budget.category, 0)
            budgets.append(
                {
                    "category": budget.category,
                    "amount_cents": budget.amount_cents,
                    "spent_cents": spent,
                    "remaining_cents": budget.amount_cents - spent,
                    "exceeded_cents": max(0, spent - budget.amount_cents),
                }
            )
        subscriptions, extra = recurrence(db, user, month)
        today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        reference = max(start, today)
        goals = list(
            db.scalars(select(Goal).where(Goal.owner == user, Goal.archived.is_(False)))
        )
        return {
            "month": month,
            "version": plan.version if plan else 0,
            "as_of": reference,
            "method": "regras-v1",
            "records_revision": records_revision,
            "plan": config,
            "figures": figures,
            "capacity_cents": capacity,
            "budgets": budgets,
            "recurrences": subscriptions,
            "goals": goal_plan(goals, capacity, reference),
            "warnings": warnings + extra,
            "disclaimer": "Simulação com registros e metas atuais, sem consultar saldo bancário. Não considera gastos ausentes nem garante economia ou prazo. Não reserva dinheiro automaticamente.",
        }


@router.put("/{month}/plan")
def save_plan(
    month: str,
    body: PlanEdit,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    with consistent_view(db):
        period(month)
        plan = lock_plan(db, user, month, body.expected_version)
        revision = (
            financial_revision(db, user, month) if body.records_complete else None
        )
        if body.records_complete and body.expected_records_revision != revision:
            raise HTTPException(
                409,
                "Registros alterados após a leitura. Recarregue e confira novamente.",
            )
        for key, value in body.model_dump(
            exclude={"expected_version", "expected_records_revision"}
        ).items():
            setattr(plan, key, value)
        plan.stats_signature = revision
        db.commit()
        return {
            **body.model_dump(
                exclude={"expected_version", "expected_records_revision"}
            ),
            "version": plan.version,
        }


@router.put("/{month}/budget")
def save_budget(
    month: str,
    body: BudgetInput,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    period(month)
    plan = lock_plan(db, user, month, body.expected_version)
    budget = db.get(Budget, (user, month, body.category))
    if not budget:
        budget = Budget(owner=user, month=month, category=body.category)
        db.add(budget)
    budget.amount_cents = body.amount_cents
    db.commit()
    return {
        **body.model_dump(exclude={"expected_version", "expected_records_revision"}),
        "version": plan.version,
    }


@router.delete("/{month}/budget/{category}", status_code=204)
def remove_budget(
    month: str,
    category: str,
    expected_version: int = Query(ge=0, le=2147483646),
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    period(month)
    lock_plan(db, user, month, expected_version)
    budget = db.get(Budget, (user, month, category))
    if budget is None:
        raise HTTPException(404, "Orçamento não encontrado")
    db.delete(budget)
    db.commit()


def lock_plan(db, user, month, expected):
    # O registro do mês permanece após remover limites: evita retorno à versão antiga.
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(
        insert(MonthPlan)
        .values(
            owner=user, month=month, version=0, buffer_cents=0, records_complete=False
        )
        .on_conflict_do_nothing()
    )
    plan = db.scalar(
        select(MonthPlan)
        .where(MonthPlan.owner == user, MonthPlan.month == month)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if plan.version != expected:
        raise HTTPException(
            409, "Planejamento alterado em outra sessão. Recarregue antes de salvar."
        )
    plan.version += 1
    return plan


@contextmanager
def consistent_view(db):
    # Iniciar antes da primeira consulta; todas as leituras usam o mesmo snapshot.
    if db.bind.dialect.name == "postgresql":
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
    try:
        yield
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) == "40001":
            db.rollback()
            raise HTTPException(
                409,
                "Planejamento alterado em outra sessão. Recarregue antes de salvar.",
            ) from None
        raise


def financial_revision(db, user, month):
    start, end = period(month)
    groups = []
    for model in (Transaction, StatementPayment):
        groups.append(
            [
                public(row)
                for row in db.scalars(
                    select(model)
                    .where(model.owner == user, model.date >= start, model.date < end)
                    .order_by(model.id)
                )
            ]
        )
    statements = list(
        db.scalars(
            select(Statement)
            .where(Statement.owner == user, Statement.month == month)
            .order_by(Statement.id)
        )
    )
    groups.append([public(row) for row in statements])
    groups.append(
        [
            public(row)
            for row in db.scalars(
                select(Charge)
                .where(
                    Charge.owner == user,
                    Charge.statement_id.in_([row.id for row in statements]),
                )
                .order_by(Charge.id)
            )
        ]
    )
    return hashlib.sha256(
        json.dumps(
            ["records-v2", user, month, groups], sort_keys=True, default=str
        ).encode()
    ).hexdigest()
