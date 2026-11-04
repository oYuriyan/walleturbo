"""Metadados versionados; arquivamento preserva os vínculos financeiros."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app.cards import AccountInput, owned, public
from app.db import (
    Account,
    Card,
    OpeningBalance,
    Transfer,
    Statement,
    StatementPayment,
    Transaction,
    db_session,
)
from app.security import current_user

router = APIRouter(prefix="/api")


class LifecycleInput(AccountInput):
    archived: bool = Field(strict=True)
    expected_version: int = Field(strict=True, ge=0, le=2147483646)


def check_version(row, expected):
    if row.version != expected:
        raise HTTPException(
            409, "Cadastro alterado em outra sessão. Atualize antes de salvar."
        )


def update(db, model, user, identifier, body):
    row = owned(db, model, user, identifier, lock=True)
    check_version(row, body.expected_version)
    if row.name != body.name or row.archived != body.archived:
        row.name, row.archived = body.name, body.archived
        row.version += 1
    db.commit()
    return public(row)


@router.put("/accounts/{account_id}")
def update_account(
    account_id: str,
    body: LifecycleInput,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    return update(db, Account, user, account_id, body)


@router.put("/cards/{card_id}")
def update_card(
    card_id: str,
    body: LifecycleInput,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    # Dia de vencimento não muda aqui: exige política própria para as faturas existentes.
    return update(db, Card, user, card_id, body)


def remove_empty(db, model, user, identifier, expected):
    row = owned(db, model, user, identifier, lock=True)
    check_version(row, expected)
    if not row.archived:
        raise HTTPException(409, "Arquive o cadastro antes de excluir.")
    references = (
        [(Statement, Statement.card_id == identifier)]
        if model is Card
        else [
            (Transaction, Transaction.account_id == identifier),
            (StatementPayment, StatementPayment.account_id == identifier),
            (OpeningBalance, OpeningBalance.account_id == identifier),
            (
                Transfer,
                or_(
                    Transfer.source_account_id == identifier,
                    Transfer.destination_account_id == identifier,
                ),
            ),
        ]
    )
    for related, condition in references:
        if db.scalar(
            select(related.id).where(related.owner == user, condition).limit(1)
        ):
            raise HTTPException(
                409,
                "Cadastro possui registros vinculados. Mantenha arquivado para preservar o histórico.",
            )
    db.delete(row)
    db.commit()


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(
    account_id: str,
    expected_version: int = Query(ge=0),
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    remove_empty(db, Account, user, account_id, expected_version)


@router.delete("/cards/{card_id}", status_code=204)
def delete_card(
    card_id: str,
    expected_version: int = Query(ge=0),
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    remove_empty(db, Card, user, card_id, expected_version)
