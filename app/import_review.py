"""Sinais limitados de possível duplicidade; nunca equivalem a identidade."""

from sqlalchemy import func, select, tuple_


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
