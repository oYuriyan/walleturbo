"""Importação OFX por FITID; marcas e recibos preservam a origem após correções."""

from uuid import NAMESPACE_URL, uuid5
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.cards import owned, require_active
from app.db import Account, RequestReceipt, Transaction, db_session
from app.import_marks import reserve
from app.import_review import (
    CSVRelease,
    ExcludedIndices,
    Links,
    OriginVersions,
    apply_links,
    candidates,
    origin_state,
    release_link,
    require_released_revision,
    select_rows,
    selection_result,
)
from app.ofx import digest, parse_ofx
from app.receipts import claim
from app.security import current_user

router = APIRouter(prefix="/api/import/ofx")


class OFXReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(max_length=256000)
    excluded_indices: ExcludedIndices = Field(default_factory=list)
    links: Links = Field(default_factory=list)
    origin_versions: OriginVersions = Field(default_factory=list)
    reviewed: bool = Field(default=False, strict=True)


class OFXInput(OFXReview):
    account_id: str = Field(min_length=1, max_length=36)


class OFXRelease(CSVRelease):
    account_id: str = Field(min_length=1, max_length=36)


def load(db, user, body, lock=False):
    require_active(owned(db, Account, user, body.account_id, lock=lock))
    try:
        parsed = parse_ofx(body.content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    keys = [
        digest(["OFX", body.account_id, identity]) for identity in parsed.identities
    ]
    return parsed, keys


def receipt_id(key):
    return str(uuid5(NAMESPACE_URL, "walleturbo/ofx/" + key))


def source_state(db, user, scope, keys, fingerprints, container=None):
    identifiers = [receipt_id(key) for key in keys]
    receipts = {
        row.request_id: row
        for row in db.scalars(
            select(RequestReceipt).where(
                RequestReceipt.owner == user,
                RequestReceipt.scope == scope,
                RequestReceipt.request_id.in_(identifiers),
            )
        )
    }
    return {
        "source_conflicts": [
            i
            for i, (identifier, fingerprint) in enumerate(
                zip(identifiers, fingerprints)
            )
            if identifier in receipts
            and receipts[identifier].payload_hash != fingerprint
        ],
        "context_conflicts": [
            i
            for i, identifier in enumerate(identifiers)
            if container
            and identifier in receipts
            and receipts[identifier].resource_id
            and receipts[identifier].resource_id != container
        ],
    }


@router.post("/preview")
def preview(
    body: OFXInput, user=Depends(current_user), db: Session = Depends(db_session)
):
    parsed, keys = load(db, user, body)
    return {
        "format": parsed.format,
        "bank_id": parsed.bank_id,
        "source_account": parsed.masked_account,
        "currency": "BRL",
        "entries": [entry.model_dump() for entry in parsed.entries],
        **source_state(db, user, "ofx", keys, parsed.fingerprints),
        **origin_state(
            db,
            Transaction,
            user,
            keys,
            Transaction.account_id == body.account_id,
            "transaction",
            "",
        ),
        "possible_duplicates": candidates(
            db,
            Transaction,
            user,
            parsed.entries,
            Transaction.account_id == body.account_id,
        ),
    }


@router.post("/confirm")
def confirm(
    body: OFXInput, user=Depends(current_user), db: Session = Depends(db_session)
):
    if not body.reviewed:
        raise HTTPException(
            422, "Confira o extrato e a conta de destino antes de confirmar."
        )
    parsed, keys = load(db, user, body, lock=True)
    selected = select_rows(parsed.entries, keys, body.excluded_indices)
    indices = {key: index for index, key in enumerate(keys)}
    # Recibos e marcas seguem ordens estáveis, inclusive em extratos reordenados.
    for _, key in sorted(selected, key=lambda item: item[1]):
        claim(db, user, "ofx", receipt_id(key), parsed.fingerprints[indices[key]])
    marks = reserve(db, user, "transaction", "", [key for _, key in selected])
    linked = apply_links(
        db,
        Transaction,
        user,
        parsed.entries,
        keys,
        body.excluded_indices,
        body.links,
        marks,
        Transaction.account_id == body.account_id,
        "transaction",
        "",
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
                select(Transaction.id).where(
                    Transaction.owner == user, Transaction.id == mark.resource_id
                )
            ):
                mark.removed = True
                removed += 1
            continue
        entry.account_id = body.account_id
        row = Transaction(owner=user, import_key=key, **entry.model_dump())
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


@router.post("/unlink")
def unlink(
    body: OFXRelease, user=Depends(current_user), db: Session = Depends(db_session)
):
    parsed, keys = load(db, user, body, lock=True)
    index = body.release.source_index
    if index >= len(keys):
        raise HTTPException(422, "Linha inválida. Refaça a prévia.")
    claim(db, user, "ofx", receipt_id(keys[index]), parsed.fingerprints[index])
    return release_link(
        db,
        Transaction,
        user,
        keys,
        body.release,
        Transaction.account_id == body.account_id,
        "transaction",
        "",
    )
