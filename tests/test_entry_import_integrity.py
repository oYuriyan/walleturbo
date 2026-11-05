from uuid import uuid4
import pytest
from tests.test_finance import ENTRY, CSV, edit_body
from tests.test_cards import setup, statement, delete_operation
from tests.test_corrections import correction
from tests.test_pdf import make_preview


def csv_card(client, s, content=None):
    return client.post(
        f"/api/statements/{s['id']}/import/confirm",
        json={
            "content": content
            or "data;descricao;valor;tipo\n2026-11-03;Mercado;10,00;despesa\n2026-11-03;Mercado;10,00;despesa\n"
        },
    )


def test_manual_request_replays_versions_deletion_and_tombstone(client, login):
    login()
    original = {**ENTRY, "request_id": str(uuid4())}
    r = client.post("/api/transactions", json=original)
    assert r.status_code == 201
    row = r.json()
    path = "/api/transactions/" + row["id"]
    assert row["version"] == 1 and row["request_id"] == original["request_id"]
    assert client.post("/api/transactions", json=original).json() == row
    change = edit_body(row, amount_cents=2000)
    updated = client.put(path, json=change).json()
    assert updated["version"] == 2 and updated["amount_cents"] == 2000
    assert client.put(path, json=change).json() == updated
    assert client.post("/api/transactions", json=original).json() == updated
    assert client.put(path, json=edit_body(row)).status_code == 409
    assert client.delete(path + "?expected_version=1").status_code == 409
    assert client.delete(path + "?expected_version=2").status_code == 204
    assert client.delete(path + "?expected_version=2").status_code == 204
    assert client.post("/api/transactions", json=original).status_code == 409
    assert client.put(path, json=change).status_code == 404
    assert (
        client.post(
            "/api/transactions", json={**original, "request_id": str(uuid4())}
        ).status_code
        == 201
    )
    assert client.get("/api/dashboard?month=2026-11").json()["expense_cents"] == 1234


def test_entry_legacy_ownership_validation_and_aba(client, login):
    login()
    row = client.post("/api/transactions", json=ENTRY).json()
    path = "/api/transactions/" + row["id"]
    assert row["request_id"] is None
    assert client.put(path, json=ENTRY).status_code == 422
    assert client.delete(path).status_code == 422
    login("bob")
    assert client.get(path).status_code == 404
    assert client.put(path, json=edit_body(row)).status_code == 404
    assert client.delete(path + "?expected_version=1").status_code == 404
    login()
    for amount in (2000, 1234):
        current = client.get(path).json()
        assert (
            client.put(path, json=edit_body(current, amount_cents=amount)).status_code
            == 200
        )
    assert client.get(path).json()["version"] == 3
    assert client.put(path, json=edit_body(row)).status_code == 409
    for changes in (
        {"expected_version": True},
        {"reason": " "},
        {"date": "9999-01-01"},
        {"date": "1899-12-31"},
    ):
        assert client.put(path, json=edit_body(row, **changes)).status_code == 422


def test_direct_csv_correction_and_deleted_origin_never_reappears(client, login):
    login()
    assert (
        client.post("/api/import/confirm", json={"content": CSV}).json()["created"] == 1
    )
    row = client.get("/api/privacy/export").json()["transactions"][0]
    path = "/api/transactions/" + row["id"]
    assert row["imported"]
    updated = client.put(
        path, json=edit_body(row, description="Conferido", amount_cents=3000)
    ).json()
    assert client.post("/api/import/confirm", json={"content": CSV}).json() == {
        "created": 0,
        "duplicates": 1,
    }
    assert client.get(path).json() == updated
    assert client.delete(path + "?expected_version=2").status_code == 204
    assert client.post("/api/import/confirm", json={"content": CSV}).json() == {
        "created": 0,
        "duplicates": 1,
        "removed": 1,
    }
    assert client.get("/api/privacy/export").json()["transactions"] == []
    markers = client.get("/api/privacy/export").json()["import_marks"]
    assert (
        len(markers) == 1 and markers[0]["removed"] and "source_key" not in markers[0]
    )


def test_card_csv_occurrences_imported_correction_and_reservations(client, login):
    _, card = setup(client, login)
    s = client.post(f"/api/cards/{card['id']}/statements?month=2026-11").json()
    assert csv_card(client, s).json()["created"] == 2
    charge = statement(client)["charges"][0]
    original = {
        "request_id": charge["operation_id"],
        "card_id": card["id"],
        "date": charge["date"],
        "description": "Conferido",
        "amount_cents": 1500,
        "kind": "expense",
        "category": "Alimentação",
        "reviewed": True,
        "first_month": "2026-11",
        "installments": 1,
    }
    path = "/api/card-operations/" + charge["operation_id"]
    data = client.get(path).json()
    assert data["origin"] == "imported" and data["editable"]
    edit = correction(client, original)
    r = client.put(path, json=edit)
    assert r.status_code == 200, r.text
    assert statement(client)["total_cents"] == 2500
    assert csv_card(client, s).json() == {"created": 0, "duplicates": 2}
    for changes in ({"first_month": "2026-12"}, {"installments": 2}):
        assert (
            client.put(path, json=correction(client, original, **changes)).status_code
            == 409
        )
    assert delete_operation(client, path).status_code == 204
    assert csv_card(client, s).json() == {"created": 0, "duplicates": 2, "removed": 1}
    triple = "data;descricao;valor;tipo\n" + "2026-11-03;Mercado;10,00;despesa\n" * 3
    assert csv_card(client, s, triple).json() == {
        "created": 1,
        "duplicates": 2,
        "removed": 1,
    }
    assert statement(client)["total_cents"] == 2000


@pytest.mark.parametrize("first", ["csv", "pdf"])
def test_csv_pdf_share_origin_and_deleted_occurrence(client, login, monkeypatch, first):
    path, payload, _ = make_preview(client, login, monkeypatch)
    s = statement(client)
    assert (
        csv_card(client, s)
        if first == "csv"
        else client.post(path + "confirm", json=payload)
    ).json()["created"] == 2
    replay = (
        client.post(path + "confirm", json=payload)
        if first == "csv"
        else csv_card(client, s)
    )
    assert replay.json() == {"created": 0, "duplicates": 2}
    charge = statement(client)["charges"][0]
    assert (
        delete_operation(
            client, "/api/card-operations/" + charge["operation_id"]
        ).status_code
        == 204
    )
    assert client.post(path + "confirm", json=payload).json() == {
        "created": 0,
        "duplicates": 2,
        "removed": 1,
    }
    assert csv_card(client, s).json() == {"created": 0, "duplicates": 2, "removed": 1}
    assert len(statement(client)["charges"]) == 1


def test_pdf_reimport_after_correcting_imported_line_preserves_current_values(
    client, login, monkeypatch
):
    path, payload, _ = make_preview(
        client, login, monkeypatch, lines=["03/11/2026 Mercado 10,00"]
    )
    assert client.post(path + "confirm", json=payload).status_code == 200
    card = client.get("/api/cards").json()[0]
    charge = statement(client)["charges"][0]
    original = {
        "request_id": charge["operation_id"],
        "card_id": card["id"],
        "date": charge["date"],
        "description": "Corrigido",
        "amount_cents": 2000,
        "kind": "expense",
        "category": "Compras",
        "reviewed": True,
        "first_month": "2026-11",
        "installments": 1,
    }
    assert (
        client.put(
            "/api/card-operations/" + charge["operation_id"],
            json=correction(client, original),
        ).status_code
        == 200
    )
    before = client.get("/api/privacy/export").json()
    assert client.post(path + "confirm", json=payload).status_code == 409
    assert client.get("/api/privacy/export").json() == before
    assert (
        delete_operation(
            client, "/api/card-operations/" + charge["operation_id"]
        ).status_code
        == 204
    )
    assert client.post(path + "confirm", json=payload).json()["removed"] == 1


def test_origin_owner_account_scope_and_privacy(client, login):
    login()
    a, b = [
        client.post("/api/accounts", json={"name": name}).json() for name in ("A", "B")
    ]
    for account in (a, b):
        assert (
            client.post(
                "/api/import/confirm",
                json={"content": CSV, "account_id": account["id"]},
            ).json()["created"]
            == 1
        )
    row = client.get("/api/privacy/export").json()["transactions"][0]
    assert (
        client.delete(
            "/api/transactions/" + row["id"] + "?expected_version=1"
        ).status_code
        == 204
    )
    login("bob")
    assert (
        client.post("/api/import/confirm", json={"content": CSV}).json()["created"] == 1
    )
    assert len(client.get("/api/privacy/export").json()["import_marks"]) == 1
    login()
    assert len(client.get("/api/privacy/export").json()["import_marks"]) == 2
    client.delete("/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"})
    login()
    assert client.get("/api/privacy/export").json()["import_marks"] == []
    assert (
        client.post("/api/import/confirm", json={"content": CSV}).json()["created"] == 1
    )


def test_failed_import_rolls_back_marks_and_finances(client, login, monkeypatch):
    from app import audit

    login()
    old = audit.snapshot

    def fail(row):
        if getattr(row, "description", None) == "Falha":
            raise RuntimeError("Falha simulada no histórico")
        return old(row)

    monkeypatch.setattr(audit, "snapshot", fail)
    content = CSV + "2026-11-04;Falha;10,00;despesa\n"
    before = client.get("/api/privacy/export").json()
    with pytest.raises(RuntimeError, match="Falha simulada"):
        client.post("/api/import/confirm", json={"content": content})
    assert client.get("/api/privacy/export").json() == before


def test_stale_card_category_and_operation_deletion_reject_updated_data(client, login):
    _, card = setup(client, login)
    s = client.post(f"/api/cards/{card['id']}/statements?month=2026-11").json()
    csv_card(client, s)
    c = statement(client)["charges"][0]
    path = "/api/card-operations/" + c["operation_id"]
    revision = client.get(path).json()["revision"]
    route = "/api/card-charges/" + c["id"] + "/review"
    assert (
        client.put(
            route,
            json={
                "category": "Compras",
                "reviewed": True,
                "expected_version": c["version"],
            },
        ).status_code
        == 200
    )
    before = client.get("/api/privacy/export").json()
    assert (
        client.put(
            route,
            json={
                "category": "Outros",
                "reviewed": True,
                "expected_version": c["version"],
            },
        ).status_code
        == 409
    )
    assert client.delete(path + "?expected_revision=" + revision).status_code == 409
    assert client.get("/api/privacy/export").json() == before
