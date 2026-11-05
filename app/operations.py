"""Correção integral de compras manuais, com prévia, revisão e idempotência."""

import hashlib
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.cards import (
    PurchaseInput,
    owned,
    public,
    fingerprint,
    require_active,
    require_open,
    statement_for,
    statement_totals,
    split_cents,
    operation_revision,
    shift_month,
)
from app.db import Card, Charge, Statement, db_session
from app.receipts import claim
from app.security import current_user

router = APIRouter(prefix="/api/card-operations")


class Correction(PurchaseInput):
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=1, max_length=160)


def load(db, user, identifier):
    first = db.scalar(
        select(Charge)
        .where(Charge.owner == user, Charge.operation_id == str(identifier))
        .order_by(Charge.installment)
    )
    if not first:
        raise HTTPException(404, "Compra não encontrada")
    statement = owned(db, Statement, user, first.statement_id)
    card = owned(db, Card, user, statement.card_id, lock=True)
    charges = list(
        db.scalars(
            select(Charge)
            .where(Charge.owner == user, Charge.operation_id == str(identifier))
            .order_by(Charge.installment)
            .execution_options(populate_existing=True)
        )
    )
    if not charges:
        raise HTTPException(404, "Compra não encontrada")
    statements = {
        s.id: s
        for s in db.scalars(
            select(Statement)
            .where(
                Statement.owner == user,
                Statement.id.in_([c.statement_id for c in charges]),
            )
            .execution_options(populate_existing=True)
        )
    }
    if any(s.card_id != card.id for s in statements.values()):
        raise HTTPException(
            409, "Operação inconsistente entre cartões; revise antes de corrigir."
        )
    revision = operation_revision(charges)
    return card, charges, statements, revision


def representation(card, charges, statements, revision):
    first = charges[0]
    return {
        "id": first.operation_id,
        "revision": revision,
        "card_id": card.id,
        "editable": all(c.import_key is None for c in charges) or len(charges) == 1,
        "origin": "imported" if any(c.import_key for c in charges) else "manual",
        "first_month": statements[first.statement_id].month,
        "date": first.date,
        "description": first.description,
        "amount_cents": sum(c.amount_cents for c in charges),
        "installments": len(charges),
        "kind": first.kind,
        "category": first.category,
        "reviewed": all(c.reviewed for c in charges),
        "charges": [public(c) for c in charges],
    }


def prepare(db, user, identifier, body):
    card, charges, statements, revision = load(db, user, identifier)
    if revision != body.expected_revision:
        raise HTTPException(
            409,
            "Compra alterada em outra sessão. Recarregue e confira a prévia novamente.",
        )
    if card.id != body.card_id:
        raise HTTPException(
            409,
            "A correção mantém o cartão original. Para trocar, registre uma nova operação explicitamente.",
        )
    if any(c.import_key is not None for c in charges) and (
        len(charges) != 1
        or body.installments != 1
        or body.first_month != statements[charges[0].statement_id].month
    ):
        raise HTTPException(
            409,
            "Linha importada mantém a fatura original e uma única parcela. Registre outra operação explicitamente para outro contexto.",
        )
    require_active(card)
    old = {}
    for c in charges:
        month = statements[c.statement_id].month
        old[month] = old.get(month, 0) + c.amount_cents * (
            -1 if c.kind == "refund" else 1
        )
    new = {
        shift_month(body.first_month, i): amount * (-1 if body.kind == "refund" else 1)
        for i, amount in enumerate(split_cents(body.amount_cents, body.installments))
    }
    months = sorted(set(old) | set(new))
    existing = {
        s.month: s
        for s in db.scalars(
            select(Statement).where(
                Statement.owner == user,
                Statement.card_id == card.id,
                Statement.month.in_(months),
            )
        )
    }
    effects = []
    for month in months:
        s = existing.get(month)
        if s:
            require_open(s)
        before = statement_totals(db, user, s)["total_cents"] if s else 0
        effects.append(
            {
                "month": month,
                "before_cents": before,
                "after_cents": before - old.get(month, 0) + new.get(month, 0),
            }
        )
    return card, charges, statements, revision, effects


@router.get("/{operation_id}")
def get_operation(
    operation_id: UUID, user=Depends(current_user), db: Session = Depends(db_session)
):
    return representation(*load(db, user, operation_id))


@router.post("/{operation_id}/preview")
def preview(
    operation_id: UUID,
    body: Correction,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    *_, revision, effects = prepare(db, user, operation_id, body)
    return {
        "revision": revision,
        "effects": effects,
        "notice": "Todas as parcelas serão corrigidas. Confira os meses e valores; nenhum pagamento bancário será realizado.",
    }


@router.put("/{operation_id}")
def correct(
    operation_id: UUID,
    body: Correction,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    # O recibo é bloqueado antes do cartão, mesma ordem dos demais escritores com UUID.
    first = db.scalar(
        select(Charge.id).where(
            Charge.owner == user, Charge.operation_id == str(operation_id)
        )
    )
    if not first:
        raise HTTPException(404, "Compra não encontrada")
    receipt = claim(
        db,
        user,
        "purchase_edit",
        body.request_id,
        hashlib.sha256((str(operation_id) + fingerprint(body)).encode()).hexdigest(),
    )
    if receipt.resource_id:
        return representation(*load(db, user, operation_id))
    card, charges, statements, revision, effects = prepare(db, user, operation_id, body)
    # Remover apenas parcelas excedentes; sobreviventes mantêm IDs e eventos de alteração.
    for charge in charges[body.installments :]:
        db.delete(charge)
    db.flush()
    for i, amount in enumerate(split_cents(body.amount_cents, body.installments)):
        statement = statement_for(db, user, card, shift_month(body.first_month, i))
        charge = (
            charges[i]
            if i < len(charges)
            else Charge(
                owner=user,
                operation_id=str(operation_id),
                payload_hash=charges[0].payload_hash,
                installment=i + 1,
            )
        )
        charge.statement_id = statement.id
        charge.date, charge.description, charge.amount_cents = (
            body.date,
            body.description,
            amount,
        )
        charge.kind, charge.category, charge.reviewed = (
            body.kind,
            body.category,
            body.reviewed,
        )
        charge.installments, charge.correction_reason = body.installments, body.reason
        db.add(charge)
    receipt.resource_id = str(operation_id)
    db.commit()
    return representation(*load(db, user, operation_id))
