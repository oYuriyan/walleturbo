"""Chaves de envio sobrevivem à exclusão isolada; expurgo do titular as remove."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.db import RequestReceipt


def claim(db, owner, scope, identifier, digest):
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(
        insert(RequestReceipt)
        .values(
            owner=owner,
            scope=scope,
            request_id=str(identifier),
            payload_hash=digest,
            cancelled=False,
        )
        .on_conflict_do_nothing()
    )
    row = db.scalar(
        select(RequestReceipt)
        .where(
            RequestReceipt.owner == owner,
            RequestReceipt.scope == scope,
            RequestReceipt.request_id == str(identifier),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row.cancelled:
        raise HTTPException(
            409,
            "Envio cancelado anteriormente. Atualize os dados; uma nova operação exige um novo identificador.",
        )
    if row.payload_hash != digest:
        raise HTTPException(409, "Identificador de envio já usado com outros dados")
    return row
