"""PDFs exclusivamente sintéticos; fluxo real no leitor isolado do Compose."""

import io
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject


def make_pdf(lines=None, pages=1, encrypted=False, active=False):
    writer = PdfWriter()
    for i in range(pages):
        page = writer.add_blank_page(width=595, height=842)
        if lines is not None:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                    NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): writer._add_object(font)}
                    )
                }
            )
            commands = ["BT /F1 10 Tf 40 800 Td 15 TL"]
            for line in lines:
                escaped = (
                    line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                )
                commands.append(f"({escaped}) Tj T*")
            commands.append("ET")
            stream = DecodedStreamObject()
            stream.set_data("\n".join(commands).encode("cp1252"))
            page[NameObject("/Contents")] = writer._add_object(stream)
    if active:
        writer._root_object[NameObject("/OpenAction")] = DictionaryObject(
            {NameObject("/S"): NameObject("/JavaScript")}
        )
    if encrypted:
        writer.encrypt("somente-teste")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def main():
    import hashlib
    import json
    import os
    import secrets
    import time
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4
    import httpx2 as httpx
    from redis import Redis

    if os.environ.get("WALLETURBO_INTEGRATION") != "1":
        raise RuntimeError("Somente ambiente de testes")
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    sid = secrets.token_hex(32)
    csrf = secrets.token_hex(32)
    key = "session:" + hashlib.sha256(sid.encode()).hexdigest()
    redis.setex(
        key,
        600,
        json.dumps(
            {
                "user": "pdf-synthetic-" + secrets.token_hex(16),
                "csrf": csrf,
                "created": time.time(),
            }
        ),
    )
    options = dict(
        base_url=os.environ["SMOKE_BASE_URL"],
        trust_env=False,
        headers={"Origin": os.environ["BASE_URL"], "X-CSRF-Token": csrf},
        cookies={"walleturbo_session": sid},
        timeout=20,
    )
    with httpx.Client(**options) as client:
        try:
            card = client.post(
                "/api/cards", json={"name": "Cartão PDF", "due_day": 10}
            ).json()
            statement = client.post(
                f"/api/cards/{card['id']}/statements?month=2026-11"
            ).json()
            path = f"/api/statements/{statement['id']}/import/pdf/"
            doc = make_pdf(
                [
                    "FATURA SINTETICA",
                    "03/11/2026 Mercado 123,45",
                    "2026-11-04 Estorno loja -23,45",
                    "Resumo nao importavel",
                ]
            )
            preview = client.post(
                path + "preview",
                content=doc,
                headers={"Content-Type": "application/pdf"},
            )
            assert preview.status_code == 200, preview.text
            data = preview.json()
            assert len(data["entries"]) == 2 and data["skipped_lines"] == 2
            assert client.get("/api/privacy/export").json()["card_charges"] == []
            entries = [
                {k: v for k, v in e.items() if k not in ("page", "line")}
                for e in data["entries"]
            ]
            body = {
                "preview_token": data["preview_token"],
                "reviewed": True,
                "entries": entries,
            }
            result = client.post(path + "confirm", json=body)
            assert result.status_code == 200, result.text
            assert result.json() == {"created": 2, "duplicates": 0}
            assert client.post(path + "confirm", json=body).json() == {
                "created": 0,
                "duplicates": 2,
            }
            summary = client.get("/api/statements?month=2026-11").json()[0]
            assert summary["total_cents"] == 10000 and summary["pending"] == 0
            scanned = client.post(
                path + "preview",
                content=make_pdf(),
                headers={"Content-Type": "application/pdf"},
            )
            assert scanned.status_code == 422 and "OCR" in scanned.json()["detail"]
            # Janela independente para a disputa adicional, sem relaxar as cotas.
            time.sleep(61)
            manual = client.post(
                "/api/card-purchases",
                json={
                    "request_id": str(uuid4()),
                    "card_id": card["id"],
                    "first_month": "2026-11",
                    "date": "2026-11-03",
                    "description": "Compra manual",
                    "amount_cents": 12345,
                    "installments": 1,
                    "kind": "expense",
                    "category": "Outros",
                    "reviewed": True,
                },
            ).json()[0]
            alias_doc = make_pdf(["03/11/2026 Outro documento 123,45"])
            alias = client.post(
                path + "preview",
                content=alias_doc,
                headers={"Content-Type": "application/pdf"},
            ).json()
            alias_body = {
                "preview_token": alias["preview_token"],
                "reviewed": True,
                "entries": [
                    {k: v for k, v in e.items() if k not in ("page", "line")}
                    for e in alias["entries"]
                ],
            }
            targets = [
                next(row for row in summary["charges"] if row["kind"] == "expense"),
                manual,
            ]
            payloads = [
                {
                    **alias_body,
                    "links": [
                        {
                            "source_index": 0,
                            "resource_id": row["id"],
                            "expected_version": row["version"],
                        }
                    ],
                }
                for row in targets
            ]
            before = client.get("/api/privacy/export").json()["card_charges"]

            def concurrent(suffix, payloads):
                def call(payload):
                    with httpx.Client(**options) as worker:
                        return worker.post(path + suffix, json=payload)

                with ThreadPoolExecutor(2) as pool:
                    return list(pool.map(call, payloads))

            linked = concurrent("confirm", payloads)
            assert sorted(r.status_code for r in linked) == [200, 409], [
                r.text for r in linked
            ]
            assert client.get("/api/privacy/export").json()["card_charges"] == before
            reviewed = client.post(
                path + "review",
                json={
                    "preview_token": alias["preview_token"],
                    "entries": alias_body["entries"],
                },
            ).json()
            origin = reviewed["known_origins"][0]
            release = {
                "preview_token": alias["preview_token"],
                "release": {
                    "source_index": 0,
                    "resource_id": origin["resource_id"],
                    "expected_version": origin["target"]["version"],
                    "expected_origin_version": origin["version"],
                    "reason": "Destino incorreto",
                },
            }
            releases = concurrent("unlink", [release, release])
            assert sorted(r.status_code for r in releases) == [200, 409], [
                r.text for r in releases
            ]
            assert client.post(path + "confirm", json=alias_body).status_code == 409
            fresh = client.post(
                path + "preview",
                content=alias_doc,
                headers={"Content-Type": "application/pdf"},
            ).json()
            accepted = next(
                payload for payload, r in zip(payloads, linked) if r.status_code == 200
            )
            remap = {
                **accepted,
                "preview_token": fresh["preview_token"],
                "links": [{**accepted["links"][0], "expected_origin_version": 2}],
            }
            assert client.post(path + "confirm", json=remap).json()["linked"] == 1
            assert client.post(path + "unlink", json=release).status_code == 409
            assert client.get("/api/privacy/export").json()["card_charges"] == before
            print(
                "PASS: PDF isolado, revisão/estorno, deduplicação, vínculo e desfazimento concorrentes, reenvio antigo recusado e remapeamento sem mudança financeira."
            )
        finally:
            assert (
                client.delete(
                    "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
                ).status_code
                == 200
            )
            redis.delete(key)


if __name__ == "__main__":
    main()
