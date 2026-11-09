"""Histórico privado de mudanças ORM, atômico com a operação financeira."""

from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, Query
from sqlalchemy import event, inspect, select, or_, and_
from sqlalchemy.orm import Session
from app.cards import owned, public
from app.db import (
    MonthPlan,
    Budget,
    Account,
    Card,
    Charge,
    FinancialAudit,
    Goal,
    OpeningBalance,
    Statement,
    StatementPayment,
    Transaction,
    Transfer,
    db_session,
)
from app.security import current_user

ENTITIES = {
    MonthPlan: "month_plan",
    Budget: "budget",
    Account: "account",
    Card: "card",
    Goal: "goal",
    Transaction: "transaction",
    Charge: "card_charge",
    Statement: "statement",
    StatementPayment: "statement_payment",
    OpeningBalance: "opening_balance",
    Transfer: "transfer",
}
PRIVATE_COLUMNS = {"owner", "payload_hash", "import_key", "stats_signature"}


def snapshot(row):
    return {
        c.name: (value.isoformat() if isinstance(value, (date, datetime)) else value)
        for c in row.__table__.columns
        if c.name not in PRIVATE_COLUMNS
        for value in [getattr(row, c.name)]
    }


def record(action):
    def write(mapper, connection, row):
        after = snapshot(row)
        before = None
        if action == "updated":
            state = inspect(row)
            changes = {
                key: attr.history
                for key, attr in state.attrs.items()
                if attr.history.has_changes()
            }
            if not changes:
                return
            before = dict(after)
            for key, history in changes.items():
                if key in before:
                    if not history.deleted:
                        # Os escritores atuais carregam a linha inteira antes de editar.
                        # Recusar estado incompleto evita inventar um valor anterior.
                        raise RuntimeError(
                            "Alteração auditada exige estado anterior carregado"
                        )
                    value = history.deleted[0]
                    before[key] = (
                        value.isoformat()
                        if isinstance(value, (date, datetime))
                        else value
                    )
        elif action == "deleted":
            before, after = after, None
        connection.execute(
            FinancialAudit.__table__.insert().values(
                id=str(uuid4()),
                owner=row.owner,
                entity=ENTITIES[type(row)],
                entity_id=(
                    row.month
                    if isinstance(row, MonthPlan)
                    else (
                        row.month + ":" + row.category
                        if isinstance(row, Budget)
                        else row.id
                    )
                ),
                action=action,
                occurred_at=datetime.now(timezone.utc).isoformat(
                    timespec="microseconds"
                ),
                before=before,
                after=after,
            )
        )

    return write


# Mapper events usam a mesma conexão/transação, inclusive nos flushes das importações.
# SQL direto/bulk não passa por aqui. A única exclusão bulk financeira é o expurgo
# de privacidade; qualquer novo escritor bulk precisa de cobertura explícita.
for model in ENTITIES:
    for signal, action in (
        ("after_insert", "created"),
        ("after_update", "updated"),
        ("after_delete", "deleted"),
    ):
        event.listen(model, signal, record(action))

router = APIRouter(prefix="/api")
Entity = Literal[
    "import_link",
    "month_plan",
    "budget",
    "account",
    "card",
    "goal",
    "transaction",
    "card_charge",
    "statement",
    "statement_payment",
    "opening_balance",
    "transfer",
]


@router.get("/history")
def history(
    entity: Entity | None = None,
    entity_id: str | None = Query(default=None, max_length=36),
    before_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=30, ge=1, le=100),
    user=Depends(current_user),
    db: Session = Depends(db_session),
):
    query = select(FinancialAudit).where(FinancialAudit.owner == user)
    if entity:
        query = query.where(FinancialAudit.entity == entity)
    if entity_id:
        query = query.where(FinancialAudit.entity_id == entity_id)
    if before_id:
        cursor = owned(db, FinancialAudit, user, before_id)
        query = query.where(
            or_(
                FinancialAudit.occurred_at < cursor.occurred_at,
                and_(
                    FinancialAudit.occurred_at == cursor.occurred_at,
                    FinancialAudit.id < cursor.id,
                ),
            )
        )
    rows = list(
        db.scalars(
            query.order_by(
                FinancialAudit.occurred_at.desc(), FinancialAudit.id.desc()
            ).limit(limit + 1)
        )
    )
    return {
        "items": [public(row) for row in rows[:limit]],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
    }
