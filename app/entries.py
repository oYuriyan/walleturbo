"""Lançamentos diretos com versões, motivos e reenvios identificados."""

import hashlib
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.balances import lock_accounts
from app.cards import owned, public, fingerprint, require_active
from app.db import Transaction, Account, RequestReceipt, db_session
from app.domain import Entry
from app.import_marks import remove
from app.receipts import claim
from app.security import current_user

router = APIRouter(prefix="/api/transactions")


class Creation(Entry):
    request_id: UUID | None = None


class Correction(Entry):
    request_id: UUID
    expected_version: int = Field(strict=True, ge=1, le=2147483646)
    reason: str = Field(min_length=1, max_length=160)


@router.get("/{entry_id}")
def get(entry_id: str, user=Depends(current_user), db: Session = Depends(db_session)):
    return public(owned(db, Transaction, user, entry_id))


@router.post("", status_code=201)
def create(
    body: Creation, user=Depends(current_user), db: Session = Depends(db_session)
):
    if body.account_id:
        owned(db, Account, user, body.account_id)
    receipt = (
        claim(db, user, "transaction", body.request_id, fingerprint(body))
        if body.request_id
        else None
    )
    if receipt and receipt.resource_id:
        return public(owned(db, Transaction, user, receipt.resource_id, lock=True))
    if body.account_id:
        require_active(owned(db, Account, user, body.account_id, lock=True))
    row = Transaction(
        owner=user,
        **body.model_dump(exclude={"request_id"}),
        request_id=str(body.request_id) if body.request_id else None
    )
    db.add(row)
    db.flush()
    if receipt:
        receipt.resource_id = row.id
    db.commit()
    return public(row)


@router.put("/{entry_id}")
def correct(
    entry_id: str,
    body: Correction,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    owned(db, Transaction, user, entry_id)
    receipt = claim(
        db,
        user,
        "transaction_edit",
        body.request_id,
        hashlib.sha256((entry_id + fingerprint(body)).encode()).hexdigest(),
    )
    row = owned(db, Transaction, user, entry_id, lock=True)
    if receipt.resource_id:
        return public(row)
    if row.version != body.expected_version:
        raise HTTPException(
            409, "Lançamento alterado em outra sessão. Recarregue antes de salvar."
        )
    lock_accounts(db, user, [i for i in (row.account_id, body.account_id) if i])
    if body.account_id and body.account_id != row.account_id:
        require_active(owned(db, Account, user, body.account_id))
    for key, value in body.model_dump(
        exclude={"request_id", "expected_version", "reason"}
    ).items():
        setattr(row, key, value)
    row.correction_reason = body.reason
    receipt.resource_id = row.id
    db.commit()
    return public(row)


@router.delete("/{entry_id}", status_code=204)
def delete(
    entry_id: str,
    expected_version: int = Query(ge=1, le=2147483646),
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    original = db.scalar(
        select(Transaction).where(Transaction.owner == user, Transaction.id == entry_id)
    )
    if not original:
        if db.scalar(
            select(RequestReceipt).where(
                RequestReceipt.owner == user,
                RequestReceipt.scope == "transaction",
                RequestReceipt.resource_id == entry_id,
                RequestReceipt.cancelled.is_(True),
            )
        ):
            return
        raise HTTPException(404, "Registro não encontrado")
    receipt = None
    if original.request_id:
        receipt = db.scalar(
            select(RequestReceipt)
            .where(
                RequestReceipt.owner == user,
                RequestReceipt.scope == "transaction",
                RequestReceipt.request_id == original.request_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if receipt is None:
            raise HTTPException(
                409,
                "Recibo de criação indisponível. Revise o registro antes de excluir.",
            )
    row = owned(db, Transaction, user, entry_id, lock=True)
    if row.version != expected_version:
        raise HTTPException(
            409, "Lançamento alterado em outra sessão. Atualize antes de excluir."
        )
    if row.import_key:
        remove(db, user, "transaction", "", row.import_key, row.id)
    if receipt:
        receipt.cancelled = True
    db.delete(row)
    db.commit()
