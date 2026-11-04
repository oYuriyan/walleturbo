"""Concorrência de arquivamento e edição de cadastros em PostgreSQL real, dados sintéticos."""

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
owner = "smoke-lifecycle-" + uuid4().hex
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
        for kind in ("accounts", "cards"):
            extra = {"due_day": 10} if kind == "cards" else {}
            row = client.post("/api/" + kind, json={"name": "Original", **extra}).json()
            path = f"/api/{kind}/{row['id']}"
            changes = [
                {"name": name, "archived": False, "expected_version": 0}
                for name in ("Primeira", "Segunda")
            ]
            responses = concurrent("PUT", path, changes)
            assert sorted(r.status_code for r in responses) == [200, 409]

            # Arquivamento disputa o mesmo lock da criação de vínculo.
            def archive():
                with httpx2.Client(**options) as worker:
                    return worker.put(
                        path,
                        json={
                            "name": "Arquivada",
                            "archived": True,
                            "expected_version": 1,
                        },
                    )

            def write():
                with httpx2.Client(**options) as worker:
                    if kind == "cards":
                        return worker.post(path + "/statements?month=2026-11")
                    return worker.post(
                        "/api/transactions",
                        json={
                            "account_id": row["id"],
                            "date": "2026-11-03",
                            "description": "Concorrente",
                            "amount_cents": 100,
                            "kind": "expense",
                            "category": "Outros",
                            "reviewed": True,
                        },
                    )

            with ThreadPoolExecutor(2) as pool:
                archived, written = pool.submit(archive), pool.submit(write)
                assert archived.result().status_code == 200
                result = written.result()
                assert result.status_code in (200, 201, 409), result.text
            # Quem adquiriu o lock primeiro determina se o vínculo existe.
            deletion = client.delete(path + "?expected_version=2")
            assert deletion.status_code == (
                409 if result.status_code != 409 else 204
            ), deletion.text
            if deletion.status_code == 409:
                persisted = next(
                    r for r in client.get("/api/" + kind).json() if r["id"] == row["id"]
                )
                assert persisted["archived"] and persisted["version"] == 2
        print(
            "PASS: edição concorrente rejeita versão obsoleta; arquivamento serializa novos vínculos e exclusão preserva registros."
        )
    finally:
        response = client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        )
        assert response.status_code == 200, response.text
        redis.delete(key)
