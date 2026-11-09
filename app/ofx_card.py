"""OFX de cartão: uma origem permanece reservada à primeira fatura aceita."""

from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.cards import owned, require_open, lock_statement, active_statement_card
from app.db import Charge, Statement, db_session
from app.import_marks import reserve
from app.import_review import (
    CSVRelease,
    apply_links,
    candidates,
    origin_state,
    release_link,
    require_released_revision,
    select_rows,
    selection_result,
)
from app.ofx import digest, parse_ofx
from app.ofx_import import OFXReview, receipt_id, source_state
from app.receipts import claim
from app.security import current_user

router = APIRouter(prefix="/api/statements")


class CardOFXInput(OFXReview):
    credits_reviewed: bool = Field(default=False, strict=True)


def load(db, user, statement_id, body, lock=False):
    statement = (
        lock_statement(db, user, statement_id)
        if lock
        else owned(db, Statement, user, statement_id)
    )
    require_open(statement)
    active_statement_card(db, user, statement)
    try:
        parsed = parse_ofx(body.content, card=True)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    keys = [
        digest(["OFX-CARD", statement.card_id, identity])
        for identity in parsed.identities
    ]
    return statement, parsed, keys


def bind_source(db, user, key, fingerprint, statement_id):
    receipt = claim(db, user, "ofx_card", receipt_id(key), fingerprint)
    if receipt.resource_id and receipt.resource_id != statement_id:
        raise HTTPException(
            409,
            "Origem já reservada em outra fatura deste cartão. Revise a fatura original.",
        )
    receipt.resource_id = statement_id


@router.post("/{statement_id}/import/ofx/preview")
def preview(
    statement_id: str,
    body: CardOFXInput,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    statement, parsed, keys = load(db, user, statement_id, body)
    return {
        "format": parsed.format,
        "bank_id": parsed.bank_id,
        "source_account": parsed.masked_account,
        "currency": "BRL",
        "statement_month": statement.month,
        "payments": parsed.payments,
        "entries": [entry.model_dump() for entry in parsed.entries],
        **source_state(db, user, "ofx_card", keys, parsed.fingerprints, statement.id),
        **origin_state(
            db,
            Charge,
            user,
            keys,
            Charge.statement_id == statement.id,
            "card",
            statement.id,
        ),
        "possible_duplicates": candidates(
            db, Charge, user, parsed.entries, Charge.statement_id == statement.id
        ),
    }


@router.post("/{statement_id}/import/ofx/confirm")
def confirm(
    statement_id: str,
    body: CardOFXInput,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    if not body.reviewed:
        raise HTTPException(
            422, "Confira a fatura e os lançamentos antes de confirmar."
        )
    statement, parsed, keys = load(db, user, statement_id, body, lock=True)
    selected = select_rows(parsed.entries, keys, body.excluded_indices)
    if (
        any(entry.kind == "refund" for entry, _ in selected)
        and not body.credits_reviewed
    ):
        raise HTTPException(
            422, "Confirme que os créditos selecionados são estornos, não pagamentos."
        )
    indices = {key: i for i, key in enumerate(keys)}
    for _, key in sorted(selected, key=lambda item: item[1]):
        bind_source(db, user, key, parsed.fingerprints[indices[key]], statement.id)
    marks = reserve(db, user, "card", statement.id, [key for _, key in selected])
    linked = apply_links(
        db,
        Charge,
        user,
        parsed.entries,
        keys,
        body.excluded_indices,
        body.links,
        marks,
        Charge.statement_id == statement.id,
        "card",
        statement.id,
    )
    created = removed = 0
    for entry, key in selected:
        mark = marks[key]
        require_released_revision(mark, body.origin_versions, indices[key])
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
        mark.version += 1
        created += 1
    db.commit()
    output = selection_result(
        len(parsed.entries), created, removed, len(body.excluded_indices)
    )
    if linked:
        output["linked"] = linked
    return output


@router.post("/{statement_id}/import/ofx/unlink")
def unlink(
    statement_id: str,
    body: CSVRelease,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    statement, parsed, keys = load(db, user, statement_id, body, lock=True)
    index = body.release.source_index
    if index >= len(keys):
        raise HTTPException(422, "Linha inválida. Refaça a prévia.")
    bind_source(db, user, keys[index], parsed.fingerprints[index], statement.id)
    return release_link(
        db,
        Charge,
        user,
        keys,
        body.release,
        Charge.statement_id == statement.id,
        "card",
        statement.id,
    )
