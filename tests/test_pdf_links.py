import pytest
from sqlalchemy import event
from app.db import FinancialAudit
from app.pdf_import import preview_key
from tests.test_pdf import make_preview
from tests.test_cards import buy, delete_operation


def target(client, amount=1000, kind="expense", month="2026-11"):
    card = client.get("/api/cards").json()[0]
    response, _ = buy(
        client,
        card,
        amount_cents=amount,
        installments=1,
        date="2026-11-03",
        description="Registro existente",
        kind=kind,
        first_month=month,
    )
    assert response.status_code == 201, response.text
    return response.json()[0]


def linked(body, row, index=0, version=0):
    return {
        **body,
        "links": [
            {
                "source_index": index,
                "resource_id": row["id"],
                "expected_version": row["version"],
                "expected_origin_version": version,
            }
        ],
    }


def release(body, row, version=1):
    return {
        "preview_token": body["preview_token"],
        "release": {
            "source_index": 0,
            "resource_id": row["id"],
            "expected_version": row["version"],
            "expected_origin_version": version,
            "reason": "Destino incorreto",
        },
    }


def reread(client, path):
    response = client.post(
        path + "preview",
        content=b"%PDF-test",
        headers={"Content-Type": "application/pdf"},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("kind", ["expense", "refund"])
def test_pdf_link_uses_reviewed_fields_keeps_original_key_and_preserves_finances(
    client, login, monkeypatch, kind
):
    path, body, _ = make_preview(client, login, monkeypatch)
    row = target(client, amount=2000, kind=kind)
    edited = {
        **body,
        "entries": [{**body["entries"][1], "amount_cents": 2000, "kind": kind}],
    }
    before = client.get("/api/privacy/export").json()
    review = client.post(
        path + "review",
        json={"preview_token": body["preview_token"], "entries": edited["entries"]},
    )
    assert review.status_code == 200, review.text
    signal = review.json()["possible_duplicates"][0]
    assert signal["source_index"] == 1 and signal["matches"][0]["id"] == row["id"]
    assert client.get("/api/privacy/export").json() == before
    response = client.post(path + "confirm", json=linked(edited, row, index=1))
    assert response.json() == {
        "created": 0,
        "duplicates": 1,
        "linked": 1,
    }, response.text
    after = client.get("/api/privacy/export").json()
    assert after["card_charges"] == before["card_charges"]
    # Descrição divergente não converte um alias em nova operação.
    assert (
        client.post(path + "confirm", json=linked(edited, row, index=1)).json()[
            "created"
        ]
        == 0
    )
    assert client.post(path + "confirm", json=edited).json()["created"] == 0
    assert len(client.get("/api/history?entity=import_link").json()["items"]) == 1
    # A posição original 1 segue reconhecida; apenas a posição 0 ainda pode criar.
    assert client.post(path + "confirm", json=body).json() == {
        "created": 1,
        "duplicates": 1,
    }
    assert (
        delete_operation(
            client, "/api/card-operations/" + row["operation_id"]
        ).status_code
        == 204
    )
    assert client.post(path + "confirm", json=edited).json()["removed"] == 1


@pytest.mark.parametrize(
    "problem",
    ["version", "amount", "kind", "statement", "owner", "excluded", "duplicate"],
)
def test_pdf_invalid_links_roll_back_entire_batch(client, login, monkeypatch, problem):
    path, body, _ = make_preview(client, login, monkeypatch)
    row = target(client, month="2026-12" if problem == "statement" else "2026-11")
    request = linked(body, row)
    if problem == "version":
        request["links"][0]["expected_version"] = 99
    elif problem == "amount":
        request["entries"][0]["amount_cents"] = 1001
    elif problem == "kind":
        request["entries"][0]["kind"] = "refund"
    elif problem == "owner":
        # O token de outro usuário nunca autoriza acesso, nem consulta nem desfazimento.
        login("bob")
    elif problem == "excluded":
        request["entries"] = request["entries"][1:]
    elif problem == "duplicate":
        request["links"].append(dict(request["links"][0]))
    before = client.get("/api/privacy/export").json()
    response = client.post(path + "confirm", json=request)
    assert response.status_code in (404, 409, 422), response.text
    assert client.get("/api/privacy/export").json() == before


def test_pdf_unlink_requires_new_upload_to_recreate_or_remap(
    client, login, monkeypatch
):
    path, body, _ = make_preview(
        client, login, monkeypatch, lines=["03/11/2026 Mercado 10,00"]
    )
    row = target(client)
    assert client.post(path + "confirm", json=linked(body, row)).status_code == 200
    current = reread(client, path)
    assert current["known_origins"][0]["releasable"]
    request = release(body, row)
    before = client.get("/api/privacy/export").json()["card_charges"]
    assert client.post(path + "unlink", json=request).json() == {"released": 1}
    assert client.get("/api/privacy/export").json()["card_charges"] == before
    assert client.post(path + "unlink", json=request).status_code == 409
    assert client.post(path + "confirm", json=body).status_code == 409
    assert client.post(path + "confirm", json=linked(body, row)).status_code == 409
    new = reread(client, path)
    assert new["origin_versions"] == [2]
    relink = linked({**body, "preview_token": new["preview_token"]}, row, version=2)
    assert client.post(path + "confirm", json=relink).json()["linked"] == 1
    assert client.post(path + "unlink", json=request).status_code == 409


def test_pdf_review_and_unlink_obey_session_expiry_and_fatura_binding(
    client, login, monkeypatch
):
    path, body, _ = make_preview(client, login, monkeypatch)
    row = target(client)
    review = {"preview_token": body["preview_token"], "entries": body["entries"]}
    request = release(body, row)
    login("bob")
    assert client.post(path + "review", json=review).status_code == 404
    assert client.post(path + "unlink", json=request).status_code == 404
    login()
    client.redis.delete(preview_key(body["preview_token"]))
    assert client.post(path + "review", json=review).status_code == 410
    assert client.post(path + "unlink", json=request).status_code == 410


def test_pdf_link_history_failure_reverts_finances_and_origin(
    client, login, monkeypatch
):
    path, body, _ = make_preview(client, login, monkeypatch)
    row = target(client)
    before = client.get("/api/privacy/export").json()

    def fail(mapper, connection, event):
        if event.entity == "import_link":
            raise RuntimeError("histórico indisponível")

    event.listen(FinancialAudit, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="histórico indisponível"):
            client.post(path + "confirm", json=linked(body, row))
    finally:
        event.remove(FinancialAudit, "before_insert", fail)
    assert client.get("/api/privacy/export").json() == before


def test_released_pdf_can_create_independent_occurrence_only_after_new_upload(
    client, login, monkeypatch
):
    path, body, _ = make_preview(
        client, login, monkeypatch, lines=["03/11/2026 Mercado 10,00"]
    )
    row = target(client)
    assert client.post(path + "confirm", json=linked(body, row)).status_code == 200
    assert client.post(path + "unlink", json=release(body, row)).status_code == 200
    new = reread(client, path)
    confirmed = {**body, "preview_token": new["preview_token"]}
    assert client.post(path + "confirm", json=confirmed).json()["created"] == 1
    assert client.post(path + "confirm", json=confirmed).json()["created"] == 0
    current = reread(client, path)
    origin = current["known_origins"][0]
    assert not origin["releasable"]
    forged = release(
        confirmed,
        {"id": origin["resource_id"], "version": origin["target"]["version"]},
        version=origin["version"],
    )
    assert client.post(path + "unlink", json=forged).status_code == 409
    assert len(client.get("/api/privacy/export").json()["card_charges"]) == 2


def test_pdf_alias_recognized_after_target_correction(client, login, monkeypatch):
    from tests.test_corrections import correction

    path, body, _ = make_preview(
        client, login, monkeypatch, lines=["03/11/2026 Mercado 10,00"]
    )
    card = client.get("/api/cards").json()[0]
    purchase, original = buy(
        client, card, amount_cents=1000, installments=1, date="2026-11-03"
    )
    row = purchase.json()[0]
    assert client.post(path + "confirm", json=linked(body, row)).status_code == 200
    changed = client.put(
        "/api/card-operations/" + original["request_id"],
        json=correction(client, original, amount_cents=3000),
    )
    assert changed.status_code == 200, changed.text
    before = client.get("/api/privacy/export").json()["card_charges"]
    assert client.post(path + "confirm", json=body).json()["created"] == 0
    assert client.post(path + "confirm", json=linked(body, row)).json()["linked"] == 1
    assert client.get("/api/privacy/export").json()["card_charges"] == before
