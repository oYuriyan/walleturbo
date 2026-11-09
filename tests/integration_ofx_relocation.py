"""Realocação OFX: duas competências disputam a mesma origem em PostgreSQL."""

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
content = Path("/tmp/card-102.ofx").read_text()
owner, sid, csrf = (
    "ofx-move-" + secrets.token_hex(12),
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
payload = {"content": content, "reviewed": True, "excluded_indices": [1, 2]}


def path(bill):
    return f"/api/statements/{bill['id']}/import/ofx"


with httpx2.Client(**options) as client:
    try:
        card = client.post(
            "/api/cards", json={"name": "Realocação sintética", "due_day": 10}
        ).json()
        bills = [
            client.post(f"/api/cards/{card['id']}/statements?month={month}").json()
            for month in ("2026-11", "2026-12", "2027-01")
        ]
        assert client.post(path(bills[0]) + "/confirm", json=payload).status_code == 200
        origin = client.post(
            path(bills[0]) + "/preview", json={"content": content}
        ).json()["known_origins"][0]
        base = {
            "content": content,
            "source_index": 0,
            "resource_id": origin["resource_id"],
            "expected_version": origin["target"]["version"],
            "expected_origin_version": origin["version"],
            "reason": "Competência corrigida na integração",
        }
        moves = []
        for bill in bills[1:]:
            change = {**base, "destination_statement_id": bill["id"]}
            review = client.post(path(bills[0]) + "/relocate/preview", json=change)
            assert review.status_code == 200, review.text
            moves.append(
                {
                    **change,
                    "expected_revision": review.json()["revision"],
                    "request_id": str(uuid4()),
                    "reviewed": True,
                }
            )

        def move(body):
            with httpx2.Client(**options) as worker:
                return worker.post(path(bills[0]) + "/relocate", json=body)

        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(move, moves))
        assert sorted(r.status_code for r in responses) == [200, 409], [
            r.text for r in responses
        ]
        winner = next(
            i for i, response in enumerate(responses) if response.status_code == 200
        )
        destination, other = bills[winner + 1], bills[2 - winner]
        exported = client.get("/api/privacy/export").json()
        assert len(exported["card_charges"]) == len(exported["import_marks"]) == 1
        row, mark = exported["card_charges"][0], exported["import_marks"][0]
        assert (
            row["id"] == base["resource_id"]
            and row["statement_id"] == mark["container_id"] == destination["id"]
        )
        assert mark["version"] == 2 and row["version"] == 2
        assert not exported["statement_payments"] and not exported["transactions"]
        assert (
            client.post(path(bills[0]) + "/relocate", json=moves[winner]).status_code
            == 200
        )
        assert client.get("/api/privacy/export").json() == exported
        assert client.post(path(bills[0]) + "/confirm", json=payload).status_code == 409
        assert client.post(path(destination) + "/confirm", json=payload).json() == {
            "created": 0,
            "duplicates": 1,
            "skipped": 2,
        }
        before = client.get("/api/privacy/export").json()
        engine = create_engine(os.environ["DATABASE_URL"])
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "SELECT id FROM card_charges WHERE owner=:owner AND id=:id FOR UPDATE"
                    ),
                    {"owner": owner, "id": row["id"]},
                )
                response = client.post(
                    path(destination) + "/relocate/preview",
                    json={
                        **base,
                        "expected_version": row["version"],
                        "expected_origin_version": mark["version"],
                        "destination_statement_id": other["id"],
                    },
                )
                assert (
                    response.status_code == 409
                    and "em alteração" in response.json()["detail"]
                ), response.text
        finally:
            engine.dispose()
        assert client.get("/api/privacy/export").json() == before
        history = client.get("/api/history?entity=import_relocation").json()["items"]
        assert (
            len(history) == 1 and history[0]["after"]["month"] == destination["month"]
        )
        print(
            "PASS: realocação OFX concorrente aceita uma competência (200/409), preserva ID/versões/histórico, reconhece reenvio no destino e recusa origem antiga e registro ocupado sem alteração parcial."
        )
    finally:
        assert (
            client.delete(
                "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
            ).status_code
            == 200
        )
        redis.delete(session_key)
