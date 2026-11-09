"""Realocação explícita da origem OFX primária, junto com seu lançamento."""

from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.cards import owned, lock_statement, require_open, statement_totals
from app.db import (
    Charge,
    ImportMark,
    RequestReceipt,
    Statement,
    FinancialAudit,
    db_session,
)
from app.import_review import lock_target
from app.ofx import digest
from app.ofx_card import load
from app.ofx_import import receipt_id
from app.receipts import claim
from app.security import current_user

router = APIRouter(prefix="/api/statements")


class Relocation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str = Field(max_length=256000)
    source_index: int = Field(strict=True, ge=0, le=499)
    resource_id: UUID
    destination_statement_id: UUID
    expected_version: int = Field(strict=True, ge=1, le=2147483646)
    expected_origin_version: int = Field(strict=True, ge=1, le=2147483646)
    reason: str = Field(min_length=3, max_length=160)


class RelocationConfirm(Relocation):
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_id: UUID
    reviewed: bool = Field(default=False, strict=True)


def prepare(db, user, statement_id, body):
    source, parsed, keys = load(db, user, statement_id, body, lock=True)
    destination = owned(db, Statement, user, str(body.destination_statement_id))
    if destination.card_id != source.card_id or destination.id == source.id:
        raise HTTPException(409, "Escolha outra fatura do mesmo cartão.")
    destination = lock_statement(db, user, destination.id)
    require_open(destination)
    if body.source_index >= len(keys):
        raise HTTPException(422, "Linha inválida. Refaça a prévia.")
    key = keys[body.source_index]
    receipt = db.scalar(
        select(RequestReceipt)
        .where(
            RequestReceipt.owner == user,
            RequestReceipt.scope == "ofx_card",
            RequestReceipt.request_id == receipt_id(key),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        not receipt
        or receipt.cancelled
        or receipt.resource_id != source.id
        or receipt.payload_hash != parsed.fingerprints[body.source_index]
    ):
        raise HTTPException(409, "Origem indisponível ou divergente. Refaça a prévia.")
    mark = db.scalar(
        select(ImportMark)
        .where(
            ImportMark.owner == user,
            ImportMark.scope == "card",
            ImportMark.container_id == source.id,
            ImportMark.source_key == key,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        not mark
        or mark.removed
        or mark.version != body.expected_origin_version
        or mark.resource_id != str(body.resource_id)
    ):
        raise HTTPException(409, "Origem alterada ou excluída. Refaça a prévia.")
    charge = lock_target(
        db, Charge, user, mark.resource_id, Charge.statement_id == source.id
    )
    if (
        not charge
        or charge.version != body.expected_version
        or charge.import_key != key
        or charge.installment != 1
        or charge.installments != 1
    ):
        raise HTTPException(
            409,
            "Somente o lançamento OFX original, disponível e sem parcelas pode mudar de competência.",
        )
    aliases = db.scalar(
        select(func.count())
        .select_from(ImportMark)
        .where(
            ImportMark.owner == user,
            ImportMark.scope == "card",
            ImportMark.resource_id == charge.id,
        )
    )
    operation_size = db.scalar(
        select(func.count())
        .select_from(Charge)
        .where(
            Charge.owner == user,
            Charge.operation_id == charge.operation_id,
        )
    )
    occupied = db.scalar(
        select(ImportMark.source_key).where(
            ImportMark.owner == user,
            ImportMark.scope == "card",
            ImportMark.container_id == destination.id,
            ImportMark.source_key == key,
        )
    ) or db.scalar(
        select(Charge.id).where(
            Charge.owner == user,
            Charge.statement_id == destination.id,
            Charge.import_key == key,
        )
    )
    if aliases != 1 or operation_size != 1 or occupied:
        raise HTTPException(
            409,
            "Origem com outros vínculos ou destino ocupado. Desfaça os vínculos adicionais antes de realocar.",
        )
    snapshots = [statement_totals(db, user, row) for row in (source, destination)]
    amount = charge.amount_cents * (-1 if charge.kind == "refund" else 1)
    effects = []
    for snapshot, delta in zip(snapshots, (-amount, amount)):
        after = snapshot["total_cents"] + delta
        if snapshot["paid_cents"] and after < snapshot["paid_cents"]:
            raise HTTPException(
                409,
                "A mudança deixaria pagamentos acima do total de uma fatura. Revise os pagamentos antes de realocar.",
            )
        effects.append(
            {
                "id": snapshot["id"],
                "month": snapshot["month"],
                "total_before_cents": snapshot["total_cents"],
                "total_after_cents": after,
                "remaining_before_cents": snapshot["remaining_cents"],
                "remaining_after_cents": after - snapshot["paid_cents"],
            }
        )
    preview = {
        "revision": digest(
            [
                "ofx_card_relocation",
                key,
                mark.version,
                *[snapshot["revision"] for snapshot in snapshots],
                body.model_dump(mode="json", include=set(Relocation.model_fields)),
            ]
        ),
        "resource_id": charge.id,
        "description": charge.description,
        "kind": charge.kind,
        "amount_cents": charge.amount_cents,
        "reason": body.reason,
        "source": effects[0],
        "destination": effects[1],
        "notice": "Move o lançamento e sua origem juntos. Preserva valores, data, conferência e ID; pagamentos e caixa não são alterados.",
    }
    return source, destination, receipt, mark, charge, preview


@router.post("/{statement_id}/import/ofx/relocate/preview")
def preview(
    statement_id: str,
    body: Relocation,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    return prepare(db, user, statement_id, body)[-1]


@router.post("/{statement_id}/import/ofx/relocate")
def relocate(
    statement_id: str,
    body: RelocationConfirm,
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    if not body.reviewed:
        raise HTTPException(
            422, "Confira o efeito nas duas faturas antes de confirmar."
        )
    request = claim(
        db,
        user,
        "ofx_card_move",
        body.request_id,
        digest([statement_id, body.model_dump(mode="json", exclude={"request_id"})]),
    )
    result = {
        "moved": 1,
        "resource_id": str(body.resource_id),
        "source_statement_id": statement_id,
        "destination_statement_id": str(body.destination_statement_id),
    }
    if request.resource_id:
        return result
    source, destination, receipt, mark, charge, review = prepare(
        db, user, statement_id, body
    )
    if review["revision"] != body.expected_revision:
        raise HTTPException(
            409, "Fatura ou prévia alterada. Simule novamente antes de confirmar."
        )
    before = {
        "month": source.month,
        "statement_id": source.id,
        "origin_version": mark.version,
        "description": charge.description,
    }
    charge.statement_id, charge.correction_reason = destination.id, body.reason
    mark.container_id, mark.version = destination.id, mark.version + 1
    receipt.resource_id, request.resource_id = destination.id, charge.id
    db.add(
        FinancialAudit(
            id=str(uuid4()),
            owner=user,
            entity="import_relocation",
            entity_id=charge.id,
            action="updated",
            occurred_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            before=before,
            after={
                **before,
                "month": destination.month,
                "statement_id": destination.id,
                "origin_version": mark.version,
                "reason": body.reason,
            },
        )
    )
    db.commit()
    return result
