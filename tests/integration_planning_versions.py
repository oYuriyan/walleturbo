"""Concorrência de lançamentos diretos e origens de importação em PostgreSQL real, dados sintéticos."""

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
owner = "smoke-entry-import-" + uuid4().hex
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


with httpx2.Client(**options) as client:
    try:
        path = "/api/planning/2026-11"

        def save(amount):
            with httpx2.Client(**options) as worker:
                return worker.put(
                    path + "/budget",
                    json={
                        "expected_version": 0,
                        "category": "Compras",
                        "amount_cents": amount,
                    },
                )

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(save, [1000, 2000]))
        assert sorted(r.status_code for r in results) == [200, 409], [
            (r.status_code, r.text) for r in results
        ]
        state = client.get(path).json()
        assert state["version"] == 1 and len(state["budgets"]) == 1
        assert (
            client.delete(path + "/budget/Compras?expected_version=1").status_code
            == 204
        )
        assert save(3000).status_code == 409
        assert client.get(path).json()["version"] == 2
        events = client.get("/api/history?entity=budget").json()["items"]
        assert len(events) == 2 and {e["action"] for e in events} == {
            "created",
            "deleted",
        }
        print(
            "PASS: criação concorrente de orçamento, versão compartilhada, exclusão sem retorno à versão antiga e histórico no PostgreSQL."
        )
    finally:
        client.delete("/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"})
        redis.delete(key)
