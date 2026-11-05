"""Concorrência e FKs de saldos/transferências em PostgreSQL real, dados sintéticos."""

import hashlib
import json
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import httpx2
from redis import Redis
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.db import engine

if os.environ.get("WALLETURBO_INTEGRATION") != "1":
    raise RuntimeError("Exige ambiente de integração")
url = os.environ["SMOKE_BASE_URL"]
owner = "smoke-balances-" + uuid4().hex
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
            client.post("/api/accounts", json={"name": name}).json()["id"]
            for name in ("A", "B")
        ]
        opening = {
            "request_id": str(uuid4()),
            "date": "2026-11-01",
            "amount_cents": 10000,
            "expected_version": 0,
            "reason": "Saldo sintético",
        }
        responses = concurrent("PUT", f"/api/accounts/{a}/opening", [opening, opening])
        assert [r.status_code for r in responses] == [200, 200]
        assert responses[0].json() == responses[1].json()
        client.put(
            f"/api/accounts/{b}/opening",
            json={**opening, "request_id": str(uuid4()), "amount_cents": 0},
        )
        corrections = [
            {
                **opening,
                "request_id": str(uuid4()),
                "expected_version": 1,
                "amount_cents": 20000,
            }
            for _ in range(2)
        ]
        responses = concurrent("PUT", f"/api/accounts/{a}/opening", corrections)
        assert sorted(r.status_code for r in responses) == [200, 409]
        transfer = {
            "request_id": str(uuid4()),
            "date": "2026-11-03",
            "amount_cents": 1234,
            "source_account_id": a,
            "destination_account_id": b,
            "description": "Transferência concorrente",
        }
        responses = concurrent("POST", "/api/transfers", [transfer, transfer])
        assert [r.status_code for r in responses] == [201, 201]
        assert responses[0].json() == responses[1].json()
        row = responses[0].json()
        report = client.get("/api/balances?as_of=2026-11-03")
        assert report.status_code == 200, report.text
        assert [a["balance_cents"] for a in report.json()["accounts"]] == [18766, 1234]
        responses = concurrent(
            "POST", f"/api/transfers/{row['id']}/reverse", [{"date": "2026-11-04"}] * 2
        )
        assert [r.status_code for r in responses] == [200, 200]
        assert (
            client.post("/api/transfers", json=transfer).json()["reversed_date"]
            == "2026-11-04"
        )
        assert len(client.get("/api/transfers").json()["items"]) == 1
        assert [
            a["balance_cents"]
            for a in client.get("/api/balances?as_of=2026-11-04").json()["accounts"]
        ] == [20000, 0]
        # Transferências em sentidos opostos devem usar a mesma ordem de locks.
        other = {
            **transfer,
            "request_id": str(uuid4()),
            "source_account_id": b,
            "destination_account_id": a,
        }
        responses = concurrent(
            "POST", "/api/transfers", [{**transfer, "request_id": str(uuid4())}, other]
        )
        assert [r.status_code for r in responses] == [201, 201]
        assert (
            client.get("/api/balances?as_of=2026-11-04").json()["total_cents"] == 20000
        )
        # Mesmo um escritor SQL sem os filtros da API não pode ligar contas de outro owner.
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO transfers(id,owner,source_account_id,destination_account_id,date,amount_cents,description,request_id,payload_hash) VALUES (:id,:owner,:a,:b,'2026-11-03',10,'Sintético',:request,:hash)"
                    ),
                    {
                        "id": str(uuid4()),
                        "owner": owner + "-other",
                        "a": a,
                        "b": b,
                        "request": str(uuid4()),
                        "hash": "0" * 64,
                    },
                )
            raise AssertionError("FK permitiu vínculo entre proprietários")
        except IntegrityError:
            pass
        print(
            "PASS: referência concorrente, versão obsoleta, transferência/reversão idempotentes, locks em ordem, saldo conservado e FK por proprietário."
        )
    finally:
        response = client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        )
        assert response.status_code == 200, response.text
        redis.delete(key)
