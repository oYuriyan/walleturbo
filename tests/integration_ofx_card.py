"""OFX de cartão sintético: reserva entre faturas em PostgreSQL real."""

import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import httpx2
from redis import Redis
from sqlalchemy import create_engine, text

if os.environ.get("WALLETURBO_INTEGRATION") != "1":
    raise RuntimeError("Exige integração sintética")
sgml, xml = Path("/tmp/card-102.ofx").read_text(), Path("/tmp/card-220.ofx").read_text()
owner, sid, csrf = (
    "ofx-card-" + secrets.token_hex(12),
    secrets.token_hex(32),
    secrets.token_hex(32),
)
redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
session_key = "session:" + hashlib.sha256(sid.encode()).hexdigest()
redis.setex(
    session_key, 600, json.dumps({"user": owner, "csrf": csrf, "created": time.time()})
)
options = dict(
    base_url=os.environ["SMOKE_BASE_URL"],
    trust_env=False,
    timeout=20,
    headers={"Origin": os.environ["BASE_URL"], "X-CSRF-Token": csrf},
    cookies={"walleturbo_session": sid},
)
payload = {"content": sgml, "reviewed": True, "credits_reviewed": True}


def path(bill):
    return f"/api/statements/{bill['id']}/import/ofx"


def concurrent(calls):
    def call(args):
        method, url, body = args
        with httpx2.Client(**options) as worker:
            return worker.request(method, url, json=body)

    with ThreadPoolExecutor(2) as pool:
        return list(pool.map(call, calls))


with httpx2.Client(**options) as client:

    def post(url, body):
        response = client.post(url, json=body)
        if response.status_code == 429:
            assert response.json()["detail"] == "Limite de importações atingido"
            time.sleep(int(response.headers["Retry-After"]))
            response = client.post(url, json=body)
        return response

    try:
        card = client.post(
            "/api/cards", json={"name": "Cartão OFX sintético", "due_day": 10}
        ).json()
        bills = [
            client.post(f"/api/cards/{card['id']}/statements?month={month}").json()
            for month in ("2026-11", "2026-12")
        ]
        before = client.get("/api/privacy/export").json()
        preview = post(path(bills[0]) + "/preview", payload)
        assert preview.status_code == 200 and len(preview.json()["payments"]) == 1
        assert client.get("/api/privacy/export").json() == before
        responses = concurrent(
            [("POST", path(bill) + "/confirm", payload) for bill in bills]
        )
        assert sorted(r.status_code for r in responses) == [200, 409], [
            r.text for r in responses
        ]
        winner = next(i for i, r in enumerate(responses) if r.status_code == 200)
        accepted, other = bills[winner], bills[1 - winner]
        assert post(
            path(accepted) + "/confirm", {**payload, "content": xml}
        ).json() == {"created": 0, "duplicates": 3}
        assert post(path(other) + "/preview", payload).json()["context_conflicts"] == [
            0,
            1,
            2,
        ]
        exported = client.get("/api/privacy/export").json()
        assert (
            len(exported["card_charges"]) == 3
            and not exported["statement_payments"]
            and not exported["transactions"]
        )
        expense = next(
            row for row in exported["card_charges"] if row["kind"] == "expense"
        )
        operation = "/api/card-operations/" + expense["operation_id"]
        revision = client.get(operation).json()["revision"]
        deleted, replayed = concurrent(
            [
                ("DELETE", operation + "?expected_revision=" + revision, None),
                ("POST", path(accepted) + "/confirm", payload),
            ]
        )
        assert deleted.status_code == 204 and replayed.status_code == 200, [
            deleted.text,
            replayed.text,
        ]
        assert post(path(accepted) + "/confirm", payload).json()["removed"] == 1
        before = client.get("/api/privacy/export").json()
        modified = {
            **payload,
            "content": sgml.replace("<TRNAMT>20.00", "<TRNAMT>25.00").replace(
                "CARD-003", "NEW-SOURCE"
            ),
        }
        assert post(path(accepted) + "/confirm", modified).status_code == 409
        assert client.get("/api/privacy/export").json() == before
        manual = client.post(
            "/api/card-purchases",
            json={
                "request_id": str(uuid4()),
                "card_id": card["id"],
                "first_month": accepted["month"],
                "date": "2026-11-03",
                "description": "Compra manual",
                "amount_cents": 12345,
                "installments": 1,
                "kind": "expense",
                "category": "Outros",
                "reviewed": True,
            },
        ).json()[0]
        linked = {
            **payload,
            "content": sgml.replace("CARD-001", "NEW-ALIAS"),
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
                        "SELECT id FROM card_charges WHERE owner=:owner AND id=:id FOR UPDATE"
                    ),
                    {"owner": owner, "id": manual["id"]},
                )
                busy = post(path(accepted) + "/confirm", linked)
                assert (
                    busy.status_code == 409 and "em alteração" in busy.json()["detail"]
                ), busy.text
        finally:
            engine.dispose()
        assert client.get("/api/privacy/export").json() == before
        assert post(path(accepted) + "/confirm", linked).json()["linked"] == 1
        assert post(path(other) + "/confirm", payload).status_code == 409
        assert (
            client.get("/api/privacy/export").json()["card_charges"]
            == before["card_charges"]
        )
        print(
            "PASS: OFX cartão reserva uma única fatura sob concorrência, reconhece XML reordenado, conserva exclusão/reenvio, rejeita origem divergente e destino ocupado sem pagamentos ou parcelas futuras."
        )
    finally:
        assert (
            client.delete(
                "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
            ).status_code
            == 200
        )
        redis.delete(session_key)
