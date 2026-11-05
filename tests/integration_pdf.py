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
        180,
        json.dumps(
            {
                "user": "pdf-synthetic-" + secrets.token_hex(16),
                "csrf": csrf,
                "created": time.time(),
            }
        ),
    )
    with httpx.Client(
        base_url=os.environ["SMOKE_BASE_URL"],
        trust_env=False,
        headers={"Origin": os.environ["BASE_URL"], "X-CSRF-Token": csrf},
        cookies={"walleturbo_session": sid},
        timeout=20,
    ) as client:
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
            print(
                "PASS: PDF no leitor isolado, prévia sem gravação, revisão, estorno, deduplicação e recusa de PDF escaneado."
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
