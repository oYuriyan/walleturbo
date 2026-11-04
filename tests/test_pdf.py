import json
import socket
import struct
import pytest
from app.pdf_worker import extract, bounded_extract
from app.pdf_import import candidates, preview_key
from app.pdf_protocol import read_packet, MAX_PDF_BYTES
from tests.integration_pdf import make_pdf
from tests.test_cards import setup


def test_text_pdf_and_full_dates_refunds_and_redaction():
    parsed = extract(
        make_pdf(
            [
                "Fatura de teste",
                "03/11/2026 Mercado 1.234,56",
                "2026-11-04 Loja -20,00",
                "04/11/2026 Cartao 4111 1111 1111 1111 10,00",
                "03/11/2026 Total da fatura 999,99",
                "31/02/2026 Invalido 10,00",
                "05/11 Sem ano 10,00",
            ]
        )
    )
    result = candidates(parsed)
    assert len(result["entries"]) == 3
    assert result["entries"][0]["amount_cents"] == 123456
    assert result["entries"][1]["kind"] == "refund"
    assert result["entries"][2]["description"] == "Cartao [número oculto]"
    assert result["skipped_lines"] == 4
    assert result["entries"][0]["page"] == 1
    assert result["entries"][0]["line"] == 2


@pytest.mark.parametrize(
    "content,error",
    [
        (b"not a pdf", "invalid_pdf"),
        (b"%PDF-invalid", "invalid_pdf"),
        (make_pdf(), "ocr_required"),
        (make_pdf(["abc"], encrypted=True), "encrypted"),
        (make_pdf(["abc"], active=True), "active_content"),
        (make_pdf(["abc"], pages=31), "too_many_pages"),
    ],
)
def test_unsupported_pdfs_are_rejected(content, error):
    assert extract(content)["error"] == error


def test_parser_child_accepts_only_bounded_output():
    result = json.loads(bounded_extract(make_pdf(["03/11/2026 Mercado 10,00"])))
    assert len(candidates(result)["entries"]) == 1


def test_protocol_rejects_oversized_length_before_reading_body():
    a, b = socket.socketpair()
    try:
        a.sendall(struct.pack("!I", MAX_PDF_BYTES + 1))
        with pytest.raises(ValueError):
            read_packet(b, MAX_PDF_BYTES)
    finally:
        a.close()
        b.close()


def make_preview(client, login, monkeypatch, lines=None):
    from app import pdf_import

    _, card = setup(client, login)
    statement = client.post(f"/api/cards/{card['id']}/statements?month=2026-11").json()
    calls = []

    def parser(content):
        calls.append(content)
        return extract(
            make_pdf(lines or ["03/11/2026 Mercado 10,00", "03/11/2026 Mercado 10,00"])
        )

    monkeypatch.setattr(pdf_import, "extract_isolated", parser)
    path = f"/api/statements/{statement['id']}/import/pdf/"
    result = client.post(
        path + "preview",
        content=b"%PDF-test",
        headers={"Content-Type": "application/pdf"},
    )
    assert result.status_code == 200, result.text
    data = result.json()
    entries = [
        {k: v for k, v in e.items() if k not in ("page", "line")}
        for e in data["entries"]
    ]
    return (
        path,
        {"preview_token": data["preview_token"], "reviewed": True, "entries": entries},
        calls,
    )


def test_preview_never_persists_finances_or_pdf(client, login, monkeypatch):
    path, body, calls = make_preview(client, login, monkeypatch)
    assert client.get("/api/privacy/export").json()["card_charges"] == []
    stored = json.loads(client.redis.get(preview_key(body["preview_token"])))
    assert stored["count"] == 2 and len(stored["source_keys"]) == 2
    assert "Mercado" not in json.dumps(stored)
    assert 0 < client.redis.ttl(preview_key(body["preview_token"])) <= 600


def test_partial_selection_preserves_identical_purchases(client, login, monkeypatch):
    path, body, _ = make_preview(client, login, monkeypatch)
    assert client.post(
        path + "confirm", json={**body, "entries": body["entries"][1:]}
    ).json() == {"created": 1, "duplicates": 0}
    assert client.post(path + "confirm", json=body).json() == {
        "created": 1,
        "duplicates": 1,
    }
    assert client.post(path + "confirm", json=body).json() == {
        "created": 0,
        "duplicates": 2,
    }
    assert len(client.get("/api/privacy/export").json()["card_charges"]) == 2


def test_review_and_unique_source_indices_required(client, login, monkeypatch):
    path, body, _ = make_preview(client, login, monkeypatch)
    assert (
        client.post(path + "confirm", json={**body, "reviewed": False}).status_code
        == 422
    )
    assert (
        client.post(
            path + "confirm", json={**body, "entries": [body["entries"][0]] * 2}
        ).status_code
        == 422
    )
    assert (
        client.post(
            path + "confirm",
            json={**body, "entries": [{**body["entries"][0], "source_index": 2}]},
        ).status_code
        == 422
    )
    assert client.get("/api/privacy/export").json()["card_charges"] == []


def test_edited_candidates_and_reimport_conflict_are_atomic(client, login, monkeypatch):
    path, body, _ = make_preview(client, login, monkeypatch)
    edited = {**body, "entries": [{**body["entries"][0], "amount_cents": 2000}]}
    assert client.post(path + "confirm", json=edited).json()["created"] == 1
    assert client.post(path + "confirm", json=body).status_code == 409
    rows = client.get("/api/privacy/export").json()["card_charges"]
    assert len(rows) == 1 and rows[0]["amount_cents"] == 2000


def test_expired_preview_and_other_owner_rejected(client, login, monkeypatch):
    path, body, calls = make_preview(client, login, monkeypatch)
    login("bob")
    assert client.post(path + "confirm", json=body).status_code == 404
    assert (
        client.post(
            path + "preview",
            content=b"%PDF-test",
            headers={"Content-Type": "application/pdf"},
        ).status_code
        == 404
    )
    assert len(calls) == 1
    login("alice")
    client.redis.delete(preview_key(body["preview_token"]))
    assert client.post(path + "confirm", json=body).status_code == 410


def test_binding_to_statement_and_session(client, login, monkeypatch):
    path, body, _ = make_preview(client, login, monkeypatch)
    card = client.get("/api/cards").json()[0]
    second = client.post(f"/api/cards/{card['id']}/statements?month=2026-12").json()
    assert (
        client.post(
            f"/api/statements/{second['id']}/import/pdf/confirm", json=body
        ).status_code
        == 410
    )
    stored = json.loads(client.redis.get(preview_key(body["preview_token"])))
    stored["session"] = "revoked"
    client.redis.set(preview_key(body["preview_token"]), json.dumps(stored))
    assert client.post(path + "confirm", json=body).status_code == 410


def test_closed_statement_blocks_confirmation(client, login, monkeypatch):
    path, body, _ = make_preview(client, login, monkeypatch)
    statement_id = path.split("/")[3]
    client.post(f"/api/statements/{statement_id}/close", json={"expected_cents": 0})
    assert client.post(path + "confirm", json=body).status_code == 409


def test_invalid_content_type_and_size_and_worker_failure(client, login, monkeypatch):
    from app import pdf_import

    path, body, calls = make_preview(client, login, monkeypatch)
    assert (
        client.post(
            path + "preview",
            content=b"%PDF-test",
            headers={"Content-Type": "text/plain"},
        ).status_code
        == 415
    )
    assert (
        client.post(
            path + "preview",
            content=b"%PDF-" + b"x" * MAX_PDF_BYTES,
            headers={"Content-Type": "application/pdf"},
        ).status_code
        == 413
    )
    assert len(calls) == 1

    def unavailable(content):
        raise OSError()

    monkeypatch.setattr(pdf_import, "extract_isolated", unavailable)
    assert (
        client.post(
            path + "preview",
            content=b"%PDF-test",
            headers={"Content-Type": "application/pdf"},
        ).status_code
        == 503
    )
    assert client.get("/api/privacy/export").json()["card_charges"] == []
