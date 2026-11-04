"""Teste concorrente com API, PostgreSQL e Redis reais; apenas dados sintéticos."""

import hashlib
import json
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import httpx
from redis import Redis
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.db import engine

if os.environ.get("WALLETURBO_INTEGRATION") != "1":
    raise RuntimeError("Exige WALLETURBO_INTEGRATION=1 em ambiente de testes")
url = os.environ["SMOKE_BASE_URL"]
redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
owner = "smoke-cards-" + uuid4().hex
sid = secrets.token_hex(32)
csrf = secrets.token_hex(32)
key = "session:" + hashlib.sha256(sid.encode()).hexdigest()
redis.setex(key, 180, json.dumps({"user": owner, "csrf": csrf, "created": time.time()}))
headers = {"Origin": os.environ["BASE_URL"], "X-CSRF-Token": csrf}
cookies = {"walleturbo_session": sid}
with httpx.Client(
    base_url=url, trust_env=False, headers=headers, cookies=cookies, timeout=15
) as client:
    try:
        account = client.post("/api/accounts", json={"name": "Conta sintética"}).json()
        card = client.post(
            "/api/cards", json={"name": "Cartão sintético", "due_day": 31}
        ).json()
        body = {
            "request_id": str(uuid4()),
            "card_id": card["id"],
            "first_month": "2028-02",
            "date": "2028-01-20",
            "description": "Compra concorrente",
            "amount_cents": 10000,
            "installments": 1,
            "category": "Compras",
            "reviewed": True,
        }

        def purchase(_):
            with httpx.Client(
                base_url=url,
                trust_env=False,
                headers=headers,
                cookies=cookies,
                timeout=15,
            ) as worker:
                return worker.post("/api/card-purchases", json=body)

        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(purchase, range(2)))
        assert [r.status_code for r in responses] == [201, 201]
        assert responses[0].json() == responses[1].json()
        statements = client.get("/api/statements?month=2028-02").json()
        assert len(statements) == 1 and statements[0]["total_cents"] == 10000
        s = statements[0]
        assert s["due_date"] == "2028-02-29"
        assert (
            client.post(
                f"/api/statements/{s['id']}/close", json={"expected_cents": 10000}
            ).status_code
            == 200
        )

        def payment(_):
            with httpx.Client(
                base_url=url,
                trust_env=False,
                headers=headers,
                cookies=cookies,
                timeout=15,
            ) as worker:
                return worker.post(
                    f"/api/statements/{s['id']}/payments",
                    json={
                        "request_id": str(uuid4()),
                        "account_id": account["id"],
                        "date": "2028-02-29",
                        "amount_cents": 7000,
                    },
                )

        with ThreadPoolExecutor(2) as pool:
            payments = list(pool.map(payment, range(2)))
        assert sorted(r.status_code for r in payments) == [201, 409], [
            (r.status_code, r.text) for r in payments
        ]
        data = client.get("/api/dashboard?month=2028-02").json()
        assert data["expense_cents"] == 10000 and data["cash_balance_cents"] == -7000
        # A FK composta recusa associação cruzada até por um escritor que ignore a API.
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO statements(id,owner,card_id,month,due_date,status) VALUES (:id,:owner,:card,'2028-03','2028-03-31','open')"
                    ),
                    {"id": str(uuid4()), "owner": owner + "-other", "card": card["id"]},
                )
            raise AssertionError("FK permitiu relação entre proprietários")
        except IntegrityError:
            pass
        print(
            "PASS: compras concorrentes idempotentes, pagamentos concorrentes limitados, competência/caixa e FK por proprietário."
        )
    finally:
        response = client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        )
        assert response.status_code == 200, response.text
        redis.delete(key)
