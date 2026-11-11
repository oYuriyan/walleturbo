"""Volume sintético de um usuário local; não é carga concorrente nem teste de escrita."""

from datetime import date
import hashlib
import json
import os
import secrets
import statistics
import time
from uuid import uuid4

import httpx2
from redis import Redis
from sqlalchemy import insert
from app.db import (
    Account,
    Card,
    Charge,
    Goal,
    OpeningBalance,
    Session,
    Statement,
    Transaction,
)

if os.environ.get("WALLETURBO_INTEGRATION") != "1":
    raise SystemExit("Somente ambiente de integração com dados sintéticos")

owner = "volume-test-" + uuid4().hex
sid, csrf = secrets.token_hex(32), secrets.token_hex(32)
redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
key = "session:" + hashlib.sha256(sid.encode()).hexdigest()
base = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")
browser = os.environ.get("VOLUME_BROWSER") == "1"
handed_off = False
months = [f"{2025 + i // 12}-{i % 12 + 1:02}" for i in range(24)]
accounts = [str(uuid4()) for _ in range(10)]
cards = [str(uuid4()) for _ in range(4)]
bills = {(month, card): str(uuid4()) for month in months for card in cards}
entries = [
    dict(
        owner=owner,
        account_id=accounts[i % 10],
        date=date.fromisoformat(months[i % 24] + "-10"),
        description=f"Registro {i:06}",
        amount_cents=10000 if i % 5 == 0 else 100,
        kind="income" if i % 5 == 0 else "expense",
        category="Renda" if i % 5 == 0 else "Outros",
        reviewed=True,
    )
    for i in range(10000)
]
selected = [row for row in entries if row["date"].isoformat().startswith("2026-11")]
income = sum(row["amount_cents"] for row in selected if row["kind"] == "income")
expense = (
    sum(row["amount_cents"] for row in selected if row["kind"] == "expense") + 10000
)
cash_total = sum(
    row["amount_cents"] * (1 if row["kind"] == "income" else -1) for row in entries
)
redis.setex(key, 180, json.dumps({"user": owner, "csrf": csrf, "created": time.time()}))

with httpx2.Client(
    base_url=base,
    timeout=10,
    trust_env=False,
    headers={"Origin": os.environ["BASE_URL"], "X-CSRF-Token": csrf},
    cookies={"walleturbo_session": sid},
) as client:
    try:
        with Session() as db:
            db.execute(
                insert(Account),
                [
                    dict(id=a, owner=owner, name=f"Conta {i + 1}")
                    for i, a in enumerate(accounts)
                ],
            )
            db.execute(
                insert(OpeningBalance),
                [
                    dict(
                        owner=owner,
                        account_id=a,
                        date=date(2025, 1, 1),
                        amount_cents=0,
                        version=1,
                        reason="Referência sintética",
                        request_id=str(uuid4()),
                        payload_hash="0" * 64,
                    )
                    for a in accounts
                ],
            )
            db.execute(
                insert(Card),
                [
                    dict(id=c, owner=owner, name=f"Cartão {i + 1}", due_day=20)
                    for i, c in enumerate(cards)
                ],
            )
            db.execute(
                insert(Statement),
                [
                    dict(
                        id=bill,
                        owner=owner,
                        card_id=card,
                        month=month,
                        due_date=date.fromisoformat(month + "-20"),
                    )
                    for (month, card), bill in bills.items()
                ],
            )
            db.execute(
                insert(Charge),
                [
                    dict(
                        owner=owner,
                        statement_id=bill,
                        date=date.fromisoformat(month + "-10"),
                        description=f"Compra {i + 1}",
                        amount_cents=100,
                        kind="expense",
                        category="Compras",
                        reviewed=True,
                        operation_id=str(uuid4()),
                        payload_hash="0" * 64,
                        installment=1,
                        installments=1,
                    )
                    for (month, card), bill in bills.items()
                    for i in range(25)
                ],
            )
            for start in range(0, len(entries), 1000):
                db.execute(insert(Transaction), entries[start : start + 1000])
            db.execute(
                insert(Goal),
                [
                    dict(
                        owner=owner,
                        name=f"Meta {i + 1}",
                        target_cents=100000,
                        saved_cents=0,
                        deadline=date(2027, 12, 31),
                    )
                    for i in range(10)
                ],
            )
            db.commit()
        report = {
            "scenario": {
                "users": 1,
                "months": 24,
                "accounts": 10,
                "cards": 4,
                "transactions": 10000,
                "charges": 2400,
                "statements": 96,
                "goals": 10,
            },
            "requests": {},
        }
        paths = [
            "/api/dashboard?month=2026-11",
            "/api/statements?month=2026-11",
            "/api/balances?as_of=2026-12-31",
            "/api/planning/2026-11",
            "/api/privacy/export",
        ]
        for path in paths:
            durations = []
            for _ in range(5):
                started = time.perf_counter()
                response = client.get(path)
                elapsed = time.perf_counter() - started
                assert (
                    response.status_code == 200
                ), f"Consulta {path}: HTTP {response.status_code}"
                data = response.json()
                if path.startswith("/api/dashboard"):
                    assert len(data["transactions"]) == len(selected)
                    assert (
                        data["income_cents"],
                        data["expense_cents"],
                        data["balance_cents"],
                    ) == (income, expense, income - expense)
                elif path.startswith("/api/statements"):
                    assert (
                        len(data) == 4 and sum(len(b["charges"]) for b in data) == 100
                    )
                elif path.startswith("/api/balances"):
                    assert (
                        len(data["accounts"]) == 10
                        and data["total_cents"] == cash_total
                    )
                elif path.startswith("/api/privacy"):
                    assert (
                        len(data["transactions"]) == 10000
                        and len(data["card_charges"]) == 2400
                    )
                    assert len(data["statements"]) == 96 and len(data["goals"]) == 10
                durations.append(elapsed * 1000)
            assert (
                max(durations) < 5000
            ), f"{path}: excedeu orçamento de 5 segundos neste ambiente"
            report["requests"][path] = {
                "samples": 5,
                "median_ms": round(statistics.median(durations), 1),
                "max_ms": round(max(durations), 1),
                "bytes": len(response.content),
            }
        if browser:
            print(
                json.dumps(
                    {
                        "sid": sid,
                        "csrf": csrf,
                        "month_count": len(selected),
                        "balance_cents": income - expense,
                        "report": report,
                    }
                )
            )
            handed_off = True
        else:
            print(
                "PASS: volume local, totais e contagens coerentes; "
                + json.dumps(report)
            )
    finally:
        if not handed_off:
            response = client.delete(
                "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
            )
            redis.delete(key)
            assert (
                response.status_code == 200
            ), "Limpeza da fixture de volume deve concluir"
