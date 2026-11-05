from uuid import uuid4
import pytest
from tests.test_balances import account, opening, transfer, balances
from tests.test_finance import ENTRY, CSV, edit_body
from tests.test_cards import buy, statement


def edit(client, kind, identifier, version=0, archived=True, name="Nome atualizado"):
    return client.put(
        f"/api/{kind}/{identifier}",
        json={"name": name, "archived": archived, "expected_version": version},
    )


@pytest.mark.parametrize("kind", ["accounts", "cards"])
def test_metadata_version_archive_reactivate_and_empty_delete(client, login, kind):
    login()
    row = client.post(
        "/api/" + kind,
        json={"name": "Original", **({"due_day": 10} if kind == "cards" else {})},
    ).json()
    assert row["version"] == 0 and row["archived"] is False
    assert (
        client.delete(f"/api/{kind}/{row['id']}?expected_version=0").status_code == 409
    )
    r = edit(client, kind, row["id"])
    assert r.status_code == 200 and r.json()["version"] == 1 and r.json()["archived"]
    assert edit(client, kind, row["id"], name="Perdida").status_code == 409
    assert (
        edit(client, kind, row["id"], version=1, archived=False).json()["version"] == 2
    )
    assert edit(client, kind, row["id"], version=2).json()["version"] == 3
    assert (
        client.delete(f"/api/{kind}/{row['id']}?expected_version=1").status_code == 409
    )
    assert (
        client.delete(f"/api/{kind}/{row['id']}?expected_version=3").status_code == 204
    )
    assert not client.get("/api/" + kind).json()


def test_archived_account_blocks_new_entries_imports_and_transfers_preserves_history(
    client, login
):
    login()
    a, b = account(client, "A"), account(client, "B")
    opening(client, a)
    entry = client.post("/api/transactions", json={**ENTRY, "account_id": a}).json()
    tr, body = transfer(client, a, b)
    assert edit(client, "accounts", a).status_code == 200
    assert (
        balances(client)["accounts"][0]["archived"]
        or balances(client)["accounts"][1]["archived"]
    )
    assert client.get("/api/dashboard?month=2026-11").json()["expense_cents"] == 1234
    assert (
        client.post("/api/transactions", json={**ENTRY, "account_id": a}).status_code
        == 409
    )
    assert (
        client.post(
            "/api/import/confirm", json={"content": CSV, "account_id": a}
        ).status_code
        == 409
    )
    assert transfer(client, b, a)[0].status_code == 409
    assert client.post("/api/transfers", json=body).json()["id"] == tr.json()["id"]
    assert (
        client.post(
            "/api/transfers/" + tr.json()["id"] + "/reverse",
            json={"date": "2026-11-04"},
        ).status_code
        == 200
    )
    # Corrigir o lançamento já vinculado é permitido; criar novo vínculo arquivado não é.
    assert (
        client.put(
            "/api/transactions/" + entry["id"],
            json=edit_body(entry, account_id=a, amount_cents=1000),
        ).status_code
        == 200
    )
    other = client.post("/api/transactions", json={**ENTRY, "account_id": b}).json()
    assert (
        client.put(
            "/api/transactions/" + other["id"], json=edit_body(other, account_id=a)
        ).status_code
        == 409
    )
    assert (
        opening(client, a, expected_version=1, amount_cents=20000)[0].status_code == 200
    )
    assert client.delete(f"/api/accounts/{a}?expected_version=1").status_code == 409
    assert edit(client, "accounts", a, version=1, archived=False).status_code == 200
    assert (
        client.post("/api/transactions", json={**ENTRY, "account_id": a}).status_code
        == 201
    )


def test_new_reference_requires_active_account(client, login):
    login()
    a = account(client)
    edit(client, "accounts", a)
    assert opening(client, a)[0].status_code == 409


def test_archived_card_can_settle_existing_bills_but_not_create_new_charges(
    client, login
):
    login()
    a = account(client)
    card = client.post("/api/cards", json={"name": "Cartão", "due_day": 10}).json()
    purchase, body = buy(client, card, amount_cents=10000, installments=1)
    bill = statement(client)
    assert edit(client, "cards", card["id"]).status_code == 200
    assert buy(client, card, installments=1)[0].status_code == 409
    assert client.post("/api/card-purchases", json=body).json() == purchase.json()
    assert (
        client.post(f"/api/cards/{card['id']}/statements?month=2026-12").status_code
        == 409
    )
    assert (
        client.post(f"/api/cards/{card['id']}/statements?month=2026-11").json()["id"]
        == bill["id"]
    )
    assert (
        client.post(
            f"/api/statements/{bill['id']}/import/preview", json={"content": CSV}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/statements/{bill['id']}/import/confirm", json={"content": CSV}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/statements/{bill['id']}/close", json={"expected_cents": 10000}
        ).status_code
        == 200
    )
    payment = {
        "request_id": str(uuid4()),
        "account_id": a,
        "date": "2026-11-10",
        "amount_cents": 5000,
    }
    r = client.post(f"/api/statements/{bill['id']}/payments", json=payment)
    assert r.status_code == 201
    edit(client, "accounts", a)
    assert (
        client.post(f"/api/statements/{bill['id']}/payments", json=payment).json()
        == r.json()
    )
    assert (
        client.post(
            f"/api/statements/{bill['id']}/payments",
            json={**payment, "request_id": str(uuid4())},
        ).status_code
        == 409
    )
    assert (
        client.delete(f"/api/cards/{card['id']}?expected_version=1").status_code == 409
    )
    assert (
        client.delete(
            "/api/statement-payments/"
            + r.json()["id"]
            + "?expected_version="
            + str(r.json()["version"])
        ).status_code
        == 204
    )
    assert client.post(f"/api/statements/{bill['id']}/reopen").status_code == 200


@pytest.mark.parametrize("kind", ["accounts", "cards"])
def test_lifecycle_isolation_validation_and_export(client, login, kind):
    login()
    row = client.post(
        "/api/" + kind,
        json={"name": "Privado", **({"due_day": 10} if kind == "cards" else {})},
    ).json()
    assert edit(client, kind, row["id"], name="   ").status_code == 422
    login("bob")
    assert edit(client, kind, row["id"]).status_code == 404
    assert (
        client.delete(f"/api/{kind}/{row['id']}?expected_version=0").status_code == 404
    )
    login()
    edit(client, kind, row["id"])
    data = client.get("/api/privacy/export").json()[kind]
    assert data[0]["archived"] and data[0]["version"] == 1
    assert data[0]["name"] == "Nome atualizado"
    assert (
        client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        ).status_code
        == 200
    )
    login()
    assert client.get("/api/privacy/export").json()[kind] == []


def test_archived_card_rejects_pdf_after_preview(client, login, monkeypatch):
    from tests.test_pdf import make_preview

    path, payload, calls = make_preview(client, login, monkeypatch)
    card = client.get("/api/cards").json()[0]
    assert edit(client, "cards", card["id"]).status_code == 200
    assert client.post(path + "confirm", json=payload).status_code == 409
    assert (
        client.post(
            path + "preview",
            content=b"%PDF-test",
            headers={"Content-Type": "application/pdf"},
        ).status_code
        == 409
    )
    assert len(calls) == 1
    assert client.get("/api/privacy/export").json()["card_charges"] == []
