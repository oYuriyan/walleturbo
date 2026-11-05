"""Concorrência e integridade de correção de pagamentos em PostgreSQL real, dados sintéticos."""

import hashlib
import json
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import httpx2
from redis import Redis

if os.environ.get("WALLETURBO_INTEGRATION") != "1":
    raise RuntimeError("Exige ambiente de integração")
url = os.environ["SMOKE_BASE_URL"]
owner = "smoke-payment-edit-" + uuid4().hex
sid, csrf = secrets.token_hex(32), secrets.token_hex(32)
redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
key = "session:" + hashlib.sha256(sid.encode()).hexdigest()
redis.setex(key, 180, json.dumps({"user": owner, "csrf": csrf, "created": time.time()}))
options = dict(
    base_url=url,
    trust_env=False,
    timeout=20,
    headers={"Origin": os.environ["BASE_URL"], "X-CSRF-Token": csrf},
    cookies={"walleturbo_session": sid},
)


def concurrent(method, path, bodies):
    def call(body):
        with httpx2.Client(**options) as worker:
            return worker.request(method, path, json=body)

    with ThreadPoolExecutor(2) as pool:
        return list(pool.map(call, bodies))


with httpx2.Client(**options) as client:
    try:
        a, b = [
            client.post("/api/accounts", json={"name": name}).json()
            for name in ("A", "B")
        ]
        for account, amount in ((a, 10000), (b, 20000)):
            r = client.put(
                f"/api/accounts/{account['id']}/opening",
                json={
                    "request_id": str(uuid4()),
                    "expected_version": 0,
                    "date": "2026-11-01",
                    "amount_cents": amount,
                    "reason": "Saldo sintético",
                },
            )
            assert r.status_code == 200, r.text
        card = client.post("/api/cards", json={"name": "Cartão", "due_day": 10}).json()
        r = client.post(
            "/api/card-purchases",
            json={
                "request_id": str(uuid4()),
                "card_id": card["id"],
                "first_month": "2026-11",
                "date": "2026-10-28",
                "description": "Sintético",
                "amount_cents": 15000,
                "installments": 1,
                "reviewed": True,
                "category": "Compras",
            },
        )
        assert r.status_code == 201, r.text
        s = client.get("/api/statements?month=2026-11").json()[0]
        assert (
            client.post(
                f"/api/statements/{s['id']}/close", json={"expected_cents": 15000}
            ).status_code
            == 200
        )
        payments = []
        for amount in (6000, 3000):
            r = client.post(
                f"/api/statements/{s['id']}/payments",
                json={
                    "request_id": str(uuid4()),
                    "account_id": a["id"],
                    "date": "2026-11-03",
                    "amount_cents": amount,
                },
            )
            assert r.status_code == 201, r.text
            payments.append(r.json())
        p = payments[0]
        path = "/api/statement-payments/" + p["id"]

        def edit_body(row, **changes):
            return {
                "request_id": str(uuid4()),
                "account_id": row["account_id"],
                "date": row["date"],
                "amount_cents": row["amount_cents"],
                "expected_version": row["version"],
                "as_of": "2026-12-31",
                "reason": "Conferência sintética",
                **changes,
            }

        preview = client.post(
            path + "/preview",
            json=edit_body(p, account_id=b["id"], date="2026-12-02", amount_cents=4000),
        )
        assert preview.status_code == 200, preview.text
        effects = {e["account_id"]: e for e in preview.json()["accounts"]}
        assert (
            effects[a["id"]]["after_cents"] == 7000
            and effects[b["id"]]["after_cents"] == 16000
        )
        responses = concurrent(
            "PUT",
            path,
            [
                edit_body(p, account_id=b["id"], amount_cents=amount)
                for amount in (4000, 5000)
            ],
        )
        assert sorted(r.status_code for r in responses) == [200, 409], [
            (r.status_code, r.text) for r in responses
        ]
        current = client.get("/api/statements?month=2026-11").json()[0]
        first = next(r for r in current["payments"] if r["id"] == p["id"])
        second = next(r for r in current["payments"] if r["id"] != p["id"])

        def call_edit(pair):
            row, amount, account = pair
            with httpx2.Client(**options) as worker:
                return worker.put(
                    "/api/statement-payments/" + row["id"],
                    json=edit_body(row, amount_cents=amount, account_id=account),
                )

        with ThreadPoolExecutor(2) as pool:
            responses = list(
                pool.map(call_edit, [(first, 10000, a["id"]), (second, 6000, b["id"])])
            )
        assert sorted(r.status_code for r in responses) == [200, 409], [
            (r.status_code, r.text) for r in responses
        ]
        s = client.get("/api/statements?month=2026-11").json()[0]
        assert s["paid_cents"] <= 15000 and s["total_cents"] == 15000
        balances = client.get("/api/balances?as_of=2026-12-31").json()
        assert balances["total_cents"] == 30000 - s["paid_cents"]
        fresh = next(r for r in s["payments"] if r["id"] == p["id"])
        assert client.delete(path + "?expected_version=1").status_code == 409

        def race(remove):
            with httpx2.Client(**options) as worker:
                return (
                    worker.delete(path + "?expected_version=" + str(fresh["version"]))
                    if remove
                    else worker.put(
                        path, json=edit_body(fresh, reason="Segunda conferência")
                    )
                )

        with ThreadPoolExecutor(2) as pool:
            removed, edited = list(pool.map(race, [True, False]))
        assert (removed.status_code, edited.status_code) in ((204, 404), (409, 200)), (
            removed.text,
            edited.text,
        )
        print(
            "PASS: correção concorrente de pagamento, limite com pagamentos distintos, saldos reconciliados e exclusão versus edição no PostgreSQL."
        )
    finally:
        response = client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        )
        assert response.status_code == 200, response.text
        redis.delete(key)
