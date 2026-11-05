"""Correção de registro de pagamento; não executa operações bancárias."""

import hashlib
from datetime import date as CivilDate
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session
from app.balances import balances, lock_accounts
from app.cards import (
    PaymentInput,
    owned,
    public,
    fingerprint,
    lock_statement,
    statement_totals,
    require_active,
)
from app.db import Account, StatementPayment, db_session
from app.receipts import claim
from app.security import current_user

router = APIRouter(prefix="/api/statement-payments")


class PaymentCorrection(PaymentInput):
    date: CivilDate = Field(ge=CivilDate(1900, 1, 1), le=CivilDate(9998, 12, 31))
    as_of: CivilDate = Field(ge=CivilDate(1900, 1, 1), le=CivilDate(9998, 12, 31))
    expected_version: int = Field(strict=True, ge=1, le=2147483646)
    reason: str = Field(min_length=1, max_length=160)


def load(db, user, identifier):
    payment = owned(db, StatementPayment, user, str(identifier))
    statement = lock_statement(db, user, payment.statement_id)
    payment = owned(db, StatementPayment, user, str(identifier), lock=True)
    return payment, statement


def representation(db, user, payment, statement):
    totals = statement_totals(db, user, statement)
    return {
        "payment": public(payment),
        "statement": {
            key: totals[key]
            for key in (
                "id",
                "month",
                "card_id",
                "total_cents",
                "paid_cents",
                "remaining_cents",
            )
        },
    }


def prepare(db, user, identifier, body):
    payment, statement = load(db, user, identifier)
    if payment.version != body.expected_version:
        raise HTTPException(
            409,
            "Pagamento alterado em outra sessão. Recarregue e confira a prévia novamente.",
        )
    if statement.status != "closed":
        raise HTTPException(
            409, "A fatura precisa estar conferida para corrigir o pagamento."
        )
    lock_accounts(db, user, [payment.account_id, body.account_id])
    target = owned(db, Account, user, body.account_id)
    if target.id != payment.account_id:
        require_active(target)
    totals = statement_totals(db, user, statement)
    other_paid = totals["paid_cents"] - payment.amount_cents
    if other_paid + body.amount_cents > totals["total_cents"]:
        raise HTTPException(
            409,
            "Pagamento corrigido excede o valor disponível da fatura considerando os demais pagamentos.",
        )
    report = balances(as_of=body.as_of, user=user, db=db)
    effects = []
    for row in report["accounts"]:
        if row["id"] not in (payment.account_id, body.account_id):
            continue
        before = row["balance_cents"]
        delta = None
        if before is not None:
            delta = 0
            if (
                row["id"] == payment.account_id
                and row["opening_date"] <= payment.date <= body.as_of
            ):
                delta += payment.amount_cents
            if (
                row["id"] == body.account_id
                and row["opening_date"] <= body.date <= body.as_of
            ):
                delta -= body.amount_cents
        effects.append(
            {
                "account_id": row["id"],
                "name": row["name"],
                "status": row["status"],
                "opening_date": row["opening_date"],
                "before_cents": before,
                "after_cents": None if before is None else before + delta,
                "delta_cents": delta,
            }
        )
    cash = {}
    old_month = payment.date.isoformat()[:7]
    new_month = body.date.isoformat()[:7]
    cash[old_month] = payment.amount_cents
    cash[new_month] = cash.get(new_month, 0) - body.amount_cents
    return (
        payment,
        statement,
        {
            "as_of": body.as_of,
            "version": payment.version,
            "accounts": effects,
            "statement": {
                "month": statement.month,
                "total_cents": totals["total_cents"],
                "paid_before_cents": totals["paid_cents"],
                "paid_after_cents": other_paid + body.amount_cents,
                "remaining_before_cents": totals["remaining_cents"],
                "remaining_after_cents": totals["total_cents"]
                - other_paid
                - body.amount_cents,
            },
            "cash_changes": [
                {"month": month, "delta_cents": amount}
                for month, amount in sorted(cash.items())
            ],
            "notice": "Simulação dos registros na data escolhida. Sem referência, saldo desconhecido; movimentos anteriores à referência não alteram o saldo. Não movimenta dinheiro no banco.",
        },
    )


@router.get("/{payment_id}")
def get_payment(
    payment_id: UUID, user=Depends(current_user), db: Session = Depends(db_session)
):
    payment, statement = load(db, user, payment_id)
    return representation(db, user, payment, statement)


@router.post("/{payment_id}/preview")
def preview(
    payment_id: UUID,
    body: PaymentCorrection,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    return prepare(db, user, payment_id, body)[2]


@router.put("/{payment_id}")
def correct(
    payment_id: UUID,
    body: PaymentCorrection,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    owned(db, StatementPayment, user, str(payment_id))
    receipt = claim(
        db,
        user,
        "payment_edit",
        body.request_id,
        hashlib.sha256((str(payment_id) + fingerprint(body)).encode()).hexdigest(),
    )
    if receipt.resource_id:
        payment, statement = load(db, user, payment_id)
        return representation(db, user, payment, statement)
    payment, statement, _ = prepare(db, user, payment_id, body)
    payment.account_id, payment.date, payment.amount_cents = (
        body.account_id,
        body.date,
        body.amount_cents,
    )
    payment.correction_reason = body.reason
    receipt.resource_id = payment.id
    db.commit()
    payment, statement = load(db, user, payment_id)
    return representation(db, user, payment, statement)
