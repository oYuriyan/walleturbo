"""Concorrência de lançamentos diretos e origens de importação em PostgreSQL real, dados sintéticos."""

import hashlib
import json
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import httpx2
from sqlalchemy import create_engine, text
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


def concurrent(method, path, bodies):
    def call(body):
        with httpx2.Client(**options) as worker:
            return worker.request(method, path, json=body)

    with ThreadPoolExecutor(2) as pool:
        return list(pool.map(call, bodies))


with httpx2.Client(**options) as client:
    try:
        original = {
            "request_id": str(uuid4()),
            "date": "2026-11-03",
            "description": "Manual sintético",
            "amount_cents": 1234,
            "kind": "expense",
            "category": "Outros",
            "reviewed": True,
        }
        responses = concurrent("POST", "/api/transactions", [original, original])
        assert [r.status_code for r in responses] == [201, 201] and responses[
            0
        ].json() == responses[1].json()
        row = responses[0].json()
        path = "/api/transactions/" + row["id"]

        def edit(current, amount):
            return {
                **{
                    key: current[key]
                    for key in (
                        "date",
                        "description",
                        "amount_cents",
                        "kind",
                        "category",
                        "reviewed",
                        "account_id",
                    )
                },
                "request_id": str(uuid4()),
                "expected_version": current["version"],
                "reason": "Conferido",
                "amount_cents": amount,
            }

        responses = concurrent("PUT", path, [edit(row, a) for a in (1500, 1600)])
        assert sorted(r.status_code for r in responses) == [200, 409], [
            (r.status_code, r.text) for r in responses
        ]
        current = client.get(path).json()

        def delete_or_edit(remove):
            with httpx2.Client(**options) as worker:
                return (
                    worker.delete(path + "?expected_version=" + str(current["version"]))
                    if remove
                    else worker.put(path, json=edit(current, 1700))
                )

        with ThreadPoolExecutor(2) as pool:
            deleted, edited = list(pool.map(delete_or_edit, [True, False]))
        assert (deleted.status_code, edited.status_code) in ((204, 404), (409, 200))
        if deleted.status_code == 409:
            latest = client.get(path).json()
            assert (
                client.delete(
                    path + "?expected_version=" + str(latest["version"])
                ).status_code
                == 204
            )
        assert client.post("/api/transactions", json=original).status_code == 409
        header = "data;descricao;valor;tipo\n"
        a = "2026-11-03;Linha A;10,00;despesa\n"
        b = "2026-11-04;Linha B;20,00;despesa\n"
        csv = header + a + b
        responses = concurrent(
            "POST",
            "/api/import/confirm",
            [{"content": csv}, {"content": header + b + a}],
        )
        assert [r.status_code for r in responses] == [200, 200], [
            (r.status_code, r.text) for r in responses
        ]
        assert sum(r.json()["created"] for r in responses) == 2
        rows = client.get("/api/privacy/export").json()["transactions"]
        assert len(rows) == 2
        row = rows[0]
        path = "/api/transactions/" + row["id"]

        def delete_or_import(remove):
            with httpx2.Client(**options) as worker:
                return (
                    worker.delete(path + "?expected_version=1")
                    if remove
                    else worker.post("/api/import/confirm", json={"content": csv})
                )

        with ThreadPoolExecutor(2) as pool:
            deleted, replayed = list(pool.map(delete_or_import, [True, False]))
        assert deleted.status_code == 204 and replayed.status_code == 200
        assert client.post("/api/import/confirm", json={"content": csv}).json() == {
            "created": 0,
            "duplicates": 2,
            "removed": 1,
        }
        card = client.post(
            "/api/cards", json={"name": "Cartão sintético", "due_day": 10}
        ).json()
        s = client.post(f"/api/cards/{card['id']}/statements?month=2026-11").json()
        import_path = f"/api/statements/{s['id']}/import/confirm"
        csv_body = {"content": header + a}
        assert client.post(import_path, json=csv_body).json()["created"] == 1
        c = client.get("/api/statements?month=2026-11").json()[0]["charges"][0]
        operation = "/api/card-operations/" + c["operation_id"]
        data = client.get(operation).json()
        correction = {
            "request_id": str(uuid4()),
            "card_id": card["id"],
            "first_month": "2026-11",
            "date": c["date"],
            "description": "Importado conferido",
            "amount_cents": 1700,
            "installments": 1,
            "kind": "expense",
            "category": "Compras",
            "reviewed": True,
            "expected_revision": data["revision"],
            "reason": "Comprovante",
        }
        result = client.put(operation, json=correction)
        assert result.status_code == 200, result.text
        revision = result.json()["revision"]
        assert client.post(import_path, json=csv_body).json() == {
            "created": 0,
            "duplicates": 1,
        }

        def delete_or_card_import(remove):
            with httpx2.Client(**options) as worker:
                return (
                    worker.delete(operation + "?expected_revision=" + revision)
                    if remove
                    else worker.post(import_path, json=csv_body)
                )

        with ThreadPoolExecutor(2) as pool:
            deleted, replayed = list(pool.map(delete_or_card_import, [True, False]))
        assert deleted.status_code == 204 and replayed.status_code == 200
        assert client.post(import_path, json=csv_body).json() == {
            "created": 0,
            "duplicates": 1,
            "removed": 1,
        }
        exported = client.get("/api/privacy/export").json()
        assert len(exported["transactions"]) == 1 and exported["card_charges"] == []
        assert (
            len(exported["import_marks"]) == 3
            and sum(m["removed"] for m in exported["import_marks"]) == 2
        )
        # Exercita a consulta com janela SQL no PostgreSQL real sem gravar.
        existing = exported["transactions"][0]
        cents = existing["amount_cents"]
        value = f"{cents // 100},{cents % 100:02d}"
        content = (
            "data;descricao;valor;tipo\n"
            f"{existing['date']};Outro documento;{value};despesa\n"
        )
        preview = client.post(
            "/api/import/preview",
            json={
                "content": content,
                "account_id": existing["account_id"],
            },
        )
        assert preview.status_code == 200, preview.text
        assert any(
            row["id"] == existing["id"]
            for row in preview.json()["possible_duplicates"][0]["matches"]
        )
        assert client.get("/api/privacy/export").json() == exported

        def confirm_selected(payload):
            response = client.post("/api/import/confirm", json=payload)
            if response.status_code == 429:
                assert response.json() == {
                    "detail": "Limite de importações atingido"
                }, response.text
                assert response.headers["Retry-After"] == "60"
                print(
                    "INFO: cota de importação preservada; aguardando janela antes de continuar seleção.",
                    flush=True,
                )
                time.sleep(61)
                response = client.post("/api/import/confirm", json=payload)
            assert response.status_code == 200, (response.status_code, response.text)
            return response.json()

        repeated = content + content.splitlines()[1] + "\n"
        selection = {
            "content": repeated,
            "account_id": existing["account_id"],
            "excluded_indices": [0],
        }
        assert confirm_selected(selection) == {
            "created": 1,
            "duplicates": 0,
            "skipped": 1,
        }
        assert confirm_selected(selection) == {
            "created": 0,
            "duplicates": 1,
            "skipped": 1,
        }
        assert confirm_selected(
            {"content": repeated, "account_id": existing["account_id"]}
        ) == {"created": 1, "duplicates": 1}
        linked_content = content.replace("Outro documento", "Origem vinculada")
        other_target = client.post(
            "/api/transactions",
            json={
                **original,
                "request_id": str(uuid4()),
                "date": existing["date"],
                "amount_cents": cents,
                "account_id": existing["account_id"],
            },
        ).json()
        bodies = [
            {
                "content": linked_content,
                "account_id": existing["account_id"],
                "links": [
                    {
                        "source_index": 0,
                        "resource_id": target["id"],
                        "expected_version": target["version"],
                    }
                ],
            }
            for target in (existing, other_target)
        ]
        linked_results = concurrent("POST", "/api/import/confirm", bodies)
        assert sorted(r.status_code for r in linked_results) == [200, 409], [
            (r.status_code, r.text) for r in linked_results
        ]
        assert confirm_selected(
            {"content": linked_content, "account_id": existing["account_id"]}
        ) == {"created": 0, "duplicates": 1}
        assert len(client.get("/api/history?entity=import_link").json()["items"]) == 1
        engine = create_engine(os.environ["DATABASE_URL"])
        busy_payload = {
            "content": content.replace("Outro documento", "Origem bloqueada"),
            "account_id": existing["account_id"],
            "links": [
                {
                    "source_index": 0,
                    "resource_id": existing["id"],
                    "expected_version": existing["version"],
                }
            ],
        }
        before_busy = client.get("/api/privacy/export").json()
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "SELECT id FROM transactions WHERE owner=:owner AND id=:id FOR UPDATE"
                    ),
                    {"owner": owner, "id": existing["id"]},
                )
                busy = client.post("/api/import/confirm", json=busy_payload)
                assert busy.status_code == 409, (busy.status_code, busy.text)
                assert (
                    busy.json()["detail"] == "Registro em alteração. Refaça a prévia."
                )
            assert client.get("/api/privacy/export").json() == before_busy
            assert confirm_selected(busy_payload)["linked"] == 1

            # Desfazer disputa a mesma origem e recusa replay de versões anteriores.
            def import_request(suffix, body):
                response = client.post("/api/import/" + suffix, json=body)
                if response.status_code == 429:
                    time.sleep(int(response.headers["Retry-After"]) + 1)
                    response = client.post("/api/import/" + suffix, json=body)
                return response

            preview_body = {
                "content": busy_payload["content"],
                "account_id": existing["account_id"],
            }
            origin = import_request("preview", preview_body).json()["known_origins"][0]
            release = {
                **preview_body,
                "release": {
                    "source_index": 0,
                    "resource_id": origin["resource_id"],
                    "expected_version": origin["target"]["version"],
                    "expected_origin_version": origin["version"],
                    "reason": "Escolha de destino incorreta",
                },
            }
            # O NOWAIT deve recusar destino ocupado e reverter a marca.
            before_release = client.get("/api/privacy/export").json()
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "SELECT id FROM transactions WHERE owner=:owner AND id=:id FOR UPDATE"
                    ),
                    {"owner": owner, "id": existing["id"]},
                )
                assert import_request("unlink", release).status_code == 409
            assert client.get("/api/privacy/export").json() == before_release
            rate_key = "rate:import:" + hashlib.sha256(owner.encode()).hexdigest()
            if int(redis.get(rate_key) or 0) > 7:
                time.sleep(max(1, redis.ttl(rate_key) + 1))
            releases = concurrent("POST", "/api/import/unlink", [release, release])
            assert sorted(r.status_code for r in releases) == [200, 409], [
                r.text for r in releases
            ]
            assert import_request("confirm", busy_payload).status_code == 409
            assert import_request("confirm", preview_body).status_code == 409
            revised = {
                **busy_payload,
                "links": [
                    {
                        **busy_payload["links"][0],
                        "resource_id": other_target["id"],
                        "expected_version": other_target["version"],
                        "expected_origin_version": 2,
                    }
                ],
            }
            assert import_request("confirm", revised).json()["linked"] == 1
            assert import_request("unlink", release).status_code == 409
        finally:
            engine.dispose()
        print(
            "PASS: UUID e edição/exclusão concorrentes, lotes em ordem inversa sem deadlock, correção importada e reimportação sem recriação no PostgreSQL."
        )
    finally:
        response = client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        )
        assert response.status_code == 200, response.text
        redis.delete(key)
