"""Identidade da linha de origem sobrevive à correção e exclusão do registro."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.db import ImportMark


def reserve(db, user, scope, container, keys):
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    marks = {}
    # Ordem estável serializa lotes concorrentes com linhas em ordens diferentes.
    for key in sorted(set(keys)):
        db.execute(
            insert(ImportMark)
            .values(
                owner=user,
                scope=scope,
                container_id=container,
                source_key=key,
                removed=False,
            )
            .on_conflict_do_nothing()
        )
        marks[key] = db.scalar(
            select(ImportMark)
            .where(
                ImportMark.owner == user,
                ImportMark.scope == scope,
                ImportMark.container_id == container,
                ImportMark.source_key == key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    return marks


def remove(db, user, scope, container, key, resource):
    mark = reserve(db, user, scope, container, [key])[key]
    mark.resource_id, mark.removed = resource, True


def result(total, created, removed):
    output = {"created": created, "duplicates": total - created}
    if removed:
        output["removed"] = removed
    return output
