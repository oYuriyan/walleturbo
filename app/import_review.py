"""Sinais limitados de possível duplicidade; nunca equivalem a identidade."""

from sqlalchemy import func, select, tuple_
from typing import Annotated
from pydantic import Field, BaseModel, ConfigDict
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy.exc import DBAPIError
from fastapi import HTTPException

ExcludedIndices = Annotated[
    list[Annotated[int, Field(strict=True, ge=0, le=499)]], Field(max_length=500)
]


class Link(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_index: int = Field(strict=True, ge=0, le=499)
    resource_id: UUID
    expected_version: int = Field(strict=True, ge=1, le=2147483646)


Links = Annotated[list[Link], Field(max_length=500)]


def apply_links(
    db, model, owner, entries, keys, excluded, links, marks, context, scope, container
):
    from app.db import FinancialAudit

    indices = [link.source_index for link in links]
    targets = [str(link.resource_id) for link in links]
    if (
        len(set(indices)) != len(indices)
        or len(set(targets)) != len(targets)
        or any(i >= len(entries) or i in excluded for i in indices)
    ):
        raise HTTPException(
            422, "Vínculos inválidos. Selecione cada origem e destino uma única vez."
        )
    linked = 0
    for link in sorted(links, key=lambda item: str(item.resource_id)):
        key = keys[link.source_index]
        mark = marks[key]
        target_id = str(link.resource_id)
        if mark.resource_id and mark.resource_id != target_id:
            raise HTTPException(
                409, "Origem já associada a outro registro. Refaça a prévia."
            )
        if mark.removed:
            continue
        if mark.resource_id:
            linked += 1
            continue
        try:
            target = db.scalar(
                select(model)
                .where(model.owner == owner, model.id == target_id, context)
                .with_for_update(nowait=True)
                .execution_options(populate_existing=True)
            )
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) != "55P03":
                raise
            db.rollback()
            raise HTTPException(
                409, "Registro em alteração. Refaça a prévia."
            ) from None
        if target is None:
            raise HTTPException(
                409, "Registro indisponível neste contexto. Refaça a prévia."
            )
        entry = entries[link.source_index]
        if target.version != link.expected_version or (
            target.date,
            target.amount_cents,
            target.kind,
        ) != (entry.date, entry.amount_cents, entry.kind):
            raise HTTPException(
                409, "Registro alterado ou incompatível. Refaça a prévia."
            )
        mark.resource_id = target.id
        db.add(
            FinancialAudit(
                id=str(uuid4()),
                owner=owner,
                entity="import_link",
                entity_id=target.id,
                action="created",
                occurred_at=datetime.now(timezone.utc).isoformat(
                    timespec="microseconds"
                ),
                before=None,
                after={
                    "scope": scope,
                    "container_id": container,
                    "resource_id": target.id,
                    "source_index": link.source_index,
                },
            )
        )
        linked += 1
    return linked


def select_rows(entries, keys, excluded):
    if len(set(excluded)) != len(excluded) or any(i >= len(entries) for i in excluded):
        raise HTTPException(422, "Seleção de linhas inválida. Refaça a prévia.")
    ignored = set(excluded)
    selected = [
        (entry, key)
        for i, (entry, key) in enumerate(zip(entries, keys))
        if i not in ignored
    ]
    if not selected:
        raise HTTPException(422, "Selecione pelo menos um lançamento para importar.")
    return selected


def selection_result(total, created, removed, skipped):
    from app.import_marks import result

    output = result(total - skipped, created, removed)
    if skipped:
        output["skipped"] = skipped
    return output


def candidates(db, model, owner, entries, context):
    keys = sorted({(e.date, e.amount_cents, e.kind) for e in entries})
    ranked = (
        select(
            model.id,
            model.date,
            model.amount_cents,
            model.kind,
            model.description,
            model.version,
            func.row_number()
            .over(
                partition_by=(model.date, model.amount_cents, model.kind),
                order_by=model.id,
            )
            .label("position"),
        )
        .where(
            model.owner == owner,
            context,
            tuple_(model.date, model.amount_cents, model.kind).in_(keys),
        )
        .subquery()
    )
    rows = db.execute(select(ranked).where(ranked.c.position <= 6)).mappings()
    groups = {}
    for row in rows:
        key = (row["date"], row["amount_cents"], row["kind"])
        groups.setdefault(key, []).append(row)
    output = []
    for index, entry in enumerate(entries):
        matches = sorted(
            groups.get((entry.date, entry.amount_cents, entry.kind), []),
            key=lambda row: row["position"],
        )
        if matches:
            output.append(
                {
                    "source_index": index,
                    "matches": [
                        {
                            "id": row["id"],
                            "date": row["date"],
                            "description": row["description"],
                            "amount_cents": row["amount_cents"],
                            "kind": row["kind"],
                            "version": row["version"],
                        }
                        for row in matches[:5]
                    ],
                    "more": len(matches) > 5,
                }
            )
    return output
