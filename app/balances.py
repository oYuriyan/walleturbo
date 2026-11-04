"""Referência revisável e transferências próprias sem duplicar receita/despesa."""

import hashlib
from datetime import date as CivilDate
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import select, func, case, union_all, and_
from sqlalchemy.orm import Session
from app.cards import Input, owned, public
from app.db import (
    Account,
    OpeningBalance,
    Transfer,
    Transaction,
    StatementPayment,
    db_session,
)
from app.security import current_user

router = APIRouter(prefix="/api")


class OpeningInput(Input):
    request_id: UUID
    date: CivilDate = Field(ge=CivilDate(1900, 1, 1), le=CivilDate(9998, 12, 31))
    amount_cents: int = Field(strict=True, ge=-99999999999, le=99999999999)
    expected_version: int = Field(strict=True, ge=0, le=2147483646)
    reason: str = Field(min_length=1, max_length=160)


class TransferInput(Input):
    request_id: UUID
    source_account_id: str = Field(min_length=1, max_length=36)
    destination_account_id: str = Field(min_length=1, max_length=36)
    date: CivilDate = Field(ge=CivilDate(1900, 1, 1), le=CivilDate(9998, 12, 31))
    amount_cents: int = Field(strict=True, gt=0, le=99999999999)
    description: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def distinct_accounts(self):
        if self.source_account_id == self.destination_account_id:
            raise ValueError("Origem e destino devem ser contas diferentes")
        return self


class ReverseInput(Input):
    date: CivilDate = Field(ge=CivilDate(1900, 1, 1), le=CivilDate(9998, 12, 31))


def digest(body, account_id=""):
    return hashlib.sha256(
        (account_id + "|" + body.model_dump_json()).encode()
    ).hexdigest()


def lock_accounts(db, owner, ids):
    # Ordem global evita deadlocks entre A→B e B→A.
    for account_id in sorted(set(ids)):
        owned(db, Account, owner, account_id, lock=True)


@router.put("/accounts/{account_id}/opening")
def set_opening(
    account_id: str,
    body: OpeningInput,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    lock_accounts(db, user, [account_id])
    fingerprint = digest(body, account_id)
    existing = db.scalar(
        select(OpeningBalance).where(
            OpeningBalance.owner == user,
            OpeningBalance.request_id == str(body.request_id),
        )
    )
    if existing:
        if existing.payload_hash != fingerprint:
            raise HTTPException(409, "Identificador já utilizado com outros dados")
        return public(existing)
    version = (
        db.scalar(
            select(func.max(OpeningBalance.version)).where(
                OpeningBalance.owner == user, OpeningBalance.account_id == account_id
            )
        )
        or 0
    )
    if body.expected_version != version:
        raise HTTPException(
            409, "Referência alterada em outra sessão. Atualize antes de corrigir."
        )
    row = OpeningBalance(
        owner=user,
        account_id=account_id,
        date=body.date,
        amount_cents=body.amount_cents,
        reason=body.reason,
        version=version + 1,
        request_id=str(body.request_id),
        payload_hash=fingerprint,
    )
    db.add(row)
    db.commit()
    return public(row)


@router.post("/transfers", status_code=201)
def create_transfer(
    body: TransferInput, user=Depends(current_user), db: Session = Depends(db_session)
):
    lock_accounts(db, user, [body.source_account_id, body.destination_account_id])
    fingerprint = digest(body)
    existing = db.scalar(
        select(Transfer).where(
            Transfer.owner == user, Transfer.request_id == str(body.request_id)
        )
    )
    if existing:
        if existing.payload_hash != fingerprint:
            raise HTTPException(409, "Identificador já utilizado com outros dados")
        return public(existing)
    row = Transfer(
        owner=user,
        payload_hash=fingerprint,
        **body.model_dump(mode="python", exclude={"request_id"}),
        request_id=str(body.request_id),
    )
    db.add(row)
    db.commit()
    return public(row)


@router.post("/transfers/{transfer_id}/reverse")
def reverse_transfer(
    transfer_id: str,
    body: ReverseInput,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    row = owned(db, Transfer, user, transfer_id)
    lock_accounts(db, user, [row.source_account_id, row.destination_account_id])
    # Recarregar depois dos locks: outra transação pode ter revertido enquanto aguardávamos.
    db.refresh(row)
    if body.date < row.date:
        raise HTTPException(422, "A reversão não pode anteceder a transferência")
    if row.reversed_date and row.reversed_date != body.date:
        raise HTTPException(409, "Transferência já revertida em outra data")
    row.reversed_date = body.date
    db.commit()
    return public(row)


@router.get("/transfers")
def transfers(
    user=Depends(current_user),
    db: Session = Depends(db_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
):
    rows = list(
        db.scalars(
            select(Transfer)
            .where(Transfer.owner == user)
            .order_by(Transfer.date.desc(), Transfer.id)
            .offset(offset)
            .limit(limit + 1)
        )
    )
    return {
        "items": [public(row) for row in rows[:limit]],
        "has_more": len(rows) > limit,
    }


@router.get("/balances")
def balances(
    as_of: CivilDate, user=Depends(current_user), db: Session = Depends(db_session)
):
    def movement(model, account, date, amount, *extra):
        return select(
            account.label("account_id"), date.label("date"), amount.label("delta")
        ).where(model.owner == user, *extra)

    moves = union_all(
        movement(
            Transaction,
            Transaction.account_id,
            Transaction.date,
            case(
                (Transaction.kind == "income", Transaction.amount_cents),
                else_=-Transaction.amount_cents,
            ),
        ),
        movement(
            StatementPayment,
            StatementPayment.account_id,
            StatementPayment.date,
            -StatementPayment.amount_cents,
        ),
        movement(
            Transfer, Transfer.source_account_id, Transfer.date, -Transfer.amount_cents
        ),
        movement(
            Transfer,
            Transfer.destination_account_id,
            Transfer.date,
            Transfer.amount_cents,
        ),
        movement(
            Transfer,
            Transfer.source_account_id,
            Transfer.reversed_date,
            Transfer.amount_cents,
            Transfer.reversed_date.is_not(None),
        ),
        movement(
            Transfer,
            Transfer.destination_account_id,
            Transfer.reversed_date,
            -Transfer.amount_cents,
            Transfer.reversed_date.is_not(None),
        ),
    ).cte("movements")
    ranked = (
        select(
            OpeningBalance,
            func.row_number()
            .over(
                partition_by=OpeningBalance.account_id,
                order_by=OpeningBalance.version.desc(),
            )
            .label("rank"),
        )
        .where(OpeningBalance.owner == user)
        .subquery()
    )
    opening = select(ranked).where(ranked.c.rank == 1).subquery()
    unassigned = (
        select(func.count(Transaction.id))
        .where(
            Transaction.owner == user,
            Transaction.account_id.is_(None),
            Transaction.date <= as_of,
        )
        .scalar_subquery()
    )
    # Uma única instrução fornece referência, movimentos e pendências no mesmo snapshot.
    statement = (
        select(
            Account.id,
            Account.name,
            opening.c.date,
            opening.c.amount_cents,
            opening.c.version,
            func.coalesce(
                func.sum(
                    case((moves.c.date >= opening.c.date, moves.c.delta), else_=0)
                ),
                0,
            ).label("net"),
            func.sum(case((moves.c.date < opening.c.date, 1), else_=0)).label(
                "excluded"
            ),
            unassigned.label("unassigned"),
        )
        .outerjoin(opening, opening.c.account_id == Account.id)
        .outerjoin(moves, and_(moves.c.account_id == Account.id, moves.c.date <= as_of))
        .where(Account.owner == user)
        .group_by(
            Account.id,
            Account.name,
            opening.c.date,
            opening.c.amount_cents,
            opening.c.version,
        )
        .order_by(Account.name, Account.id)
    )
    rows = db.execute(statement).all()
    result = []
    for row in rows:
        known = row.date is not None and row.date <= as_of
        result.append(
            {
                "id": row.id,
                "name": row.name,
                "opening_date": row.date,
                "opening_cents": row.amount_cents,
                "version": row.version or 0,
                "balance_cents": int(row.amount_cents + row.net) if known else None,
                "movement_cents": int(row.net) if known else None,
                "excluded_movements": int(row.excluded or 0),
                "status": (
                    "known"
                    if known
                    else "before_reference" if row.date else "missing_reference"
                ),
            }
        )
    missing = sum(row["balance_cents"] is None for row in result)
    unassigned_count = rows[0].unassigned if rows else db.scalar(select(unassigned))
    subtotal = sum(row["balance_cents"] or 0 for row in result)
    return {
        "as_of": as_of,
        "accounts": result,
        "known_subtotal_cents": subtotal,
        "total_cents": (
            subtotal if result and not missing and not unassigned_count else None
        ),
        "unknown_accounts": missing,
        "unassigned_transactions": unassigned_count,
    }
