"""Sinais limitados de possível duplicidade; nunca equivalem a identidade."""

from sqlalchemy import func, select, tuple_
from typing import Annotated
from pydantic import Field
from fastapi import HTTPException

ExcludedIndices = Annotated[
    list[Annotated[int, Field(strict=True, ge=0, le=499)]], Field(max_length=500)
]


def select_rows(entries, keys, excluded):
    if len(set(excluded)) != len(excluded) or any(i >= len(entries) for i in excluded):
        raise HTTPException(422, "Seleção de linhas inválida. Refaça a prévia.")
    ignored = set(excluded)
    selected = [(entry, key) for i, (entry, key) in enumerate(zip(entries, keys))
                if i not in ignored]
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
    ranked = select(
        model.id, model.date, model.amount_cents, model.kind, model.description,
        func.row_number().over(
            partition_by=(model.date, model.amount_cents, model.kind),
            order_by=model.id,
        ).label("position"),
    ).where(
        model.owner == owner, context,
        tuple_(model.date, model.amount_cents, model.kind).in_(keys),
    ).subquery()
    rows = db.execute(select(ranked).where(ranked.c.position <= 6)).mappings()
    groups = {}
    for row in rows:
        key = (row["date"], row["amount_cents"], row["kind"])
        groups.setdefault(key, []).append(row)
    output = []
    for index, entry in enumerate(entries):
        matches = sorted(groups.get((entry.date, entry.amount_cents, entry.kind), []),
                         key=lambda row: row["position"])
        if matches:
            output.append({
                "source_index": index,
                "matches": [{"id": row["id"], "date": row["date"],
                             "description": row["description"],
                             "amount_cents": row["amount_cents"], "kind": row["kind"]}
                            for row in matches[:5]],
                "more": len(matches) > 5,
            })
    return output
