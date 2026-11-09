"""OFX sintético: identidade e concorrência em PostgreSQL/Redis reais."""

import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
import httpx2
from redis import Redis
from sqlalchemy import create_engine, text

if os.environ.get("WALLETURBO_INTEGRATION") != "1":
    raise RuntimeError("Exige ambiente de integração sintético")
sgml = Path("/tmp/bank-102.ofx").read_text()
xml = Path("/tmp/bank-220.ofx").read_text()
owner, sid, csrf = (
    "ofx-synthetic-" + secrets.token_hex(12),
    secrets.token_hex(32),
    secrets.token_hex(32),
)
redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
key = "session:" + hashlib.sha256(sid.encode()).hexdigest()
redis.setex(key, 600, json.dumps({"user": owner, "csrf": csrf, "created": time.time()}))
options = dict(
    base_url=os.environ["SMOKE_BASE_URL"],
    trust_env=False,
    timeout=20,
    headers={"Origin": os.environ["BASE_URL"], "X-CSRF-Token": csrf},
    cookies={"walleturbo_session": sid},
)
base = "/api/import/ofx"


def concurrent(calls):
    def call(args):
        method, path, payload = args
        with httpx2.Client(**options) as worker:
            return worker.request(method, path, json=payload)

    with ThreadPoolExecutor(2) as pool:
        return list(pool.map(call, calls))


with httpx2.Client(**options) as client:
    try:
        acct = client.post(
            "/api/accounts", json={"name": "Conta OFX sintética"}
        ).json()["id"]
        body = {"account_id": acct, "content": sgml, "reviewed": True}
        before = client.get("/api/privacy/export").json()
        assert client.post(base + "/preview", json=body).status_code == 200
        assert client.get("/api/privacy/export").json() == before
        responses = concurrent(
            [
                ("POST", base + "/confirm", body),
                ("POST", base + "/confirm", {**body, "content": xml}),
            ]
        )
        assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
        assert sorted(r.json()["created"] for r in responses) == [0, 3]
        exported = client.get("/api/privacy/export").json()
        assert len(exported["transactions"]) == 3 and len(exported["import_marks"]) == 3
        changed = {
            **body,
            "content": sgml.replace("SYNTHETIC-001", "NEW-SOURCE").replace(
                "2500.00", "2600.00"
            ),
        }
        assert client.post(base + "/confirm", json=changed).status_code == 409
        assert client.get("/api/privacy/export").json() == exported
        expense = next(
            row for row in exported["transactions"] if row["kind"] == "expense"
        )
        deleted, replayed = concurrent(
            [
                (
                    "DELETE",
                    f"/api/transactions/{expense['id']}?expected_version={expense['version']}",
                    None,
                ),
                ("POST", base + "/confirm", body),
            ]
        )
        assert deleted.status_code == 204 and replayed.status_code == 200
        assert client.post(base + "/confirm", json=body).json()["removed"] == 1
        manual = client.post(
            "/api/transactions",
            json={
                "account_id": acct,
                "date": "2026-11-03",
                "description": "Destino manual OFX",
                "amount_cents": 1234,
                "kind": "expense",
                "category": "Outros",
            },
        ).json()
        linked = {
            **body,
            "content": sgml.replace("SYNTHETIC-001", "ALIAS-SOURCE"),
            "excluded_indices": [1, 2],
            "links": [
                {
                    "source_index": 0,
                    "resource_id": manual["id"],
                    "expected_version": manual["version"],
                }
            ],
        }
        before = client.get("/api/privacy/export").json()
        engine = create_engine(os.environ["DATABASE_URL"])
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "SELECT id FROM transactions WHERE owner=:owner AND id=:id FOR UPDATE"
                    ),
                    {"owner": owner, "id": manual["id"]},
                )
                busy = client.post(base + "/confirm", json=linked)
                assert (
                    busy.status_code == 409 and "em alteração" in busy.json()["detail"]
                ), busy.text
        finally:
            engine.dispose()
        assert client.get("/api/privacy/export").json() == before
        assert client.post(base + "/confirm", json=linked).json()["linked"] == 1
        released = client.post(
            base + "/unlink",
            json={
                "content": linked["content"],
                "account_id": acct,
                "release": {
                    **linked["links"][0],
                    "expected_origin_version": 1,
                    "reason": "Escolha incorreta",
                },
            },
        )
        assert released.status_code == 200, released.text
        assert client.post(base + "/confirm", json=linked).status_code == 409
        assert (
            client.get("/api/privacy/export").json()["transactions"]
            == before["transactions"]
        )
        print(
            "PASS: OFX 1/2 concorrentes e reordenados sem duplicação, FITID divergente atômico, exclusão/reenvio, NOWAIT e vínculo/desfazimento sem mudança financeira."
        )
    finally:
        assert (
            client.delete(
                "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
            ).status_code
            == 200
        )
        redis.delete(key)
