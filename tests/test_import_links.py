from uuid import uuid4
import pytest
from sqlalchemy import event
from app.db import FinancialAudit
from tests.test_finance import ENTRY, CSV, edit_body
from tests.test_balances import account
from tests.test_cards import setup, buy, statement, delete_operation


def payload(row, content=CSV, **changes):
    return {
        "content": content,
        "links": [
            {
                "source_index": 0,
                "resource_id": row["id"],
                "expected_version": row["version"],
            }
        ],
        **changes,
    }


def test_link_keeps_finances_replays_after_edit_and_does_not_recreate_deleted(
    client, login
):
    login()
    row = client.post(
        "/api/transactions", json={**ENTRY, "description": "Descrição manual"}
    ).json()
    body = payload(row)
    path = "/api/import/confirm"
    before = client.get("/api/dashboard?month=2026-11").json()
    assert client.post(path, json=body).json() == {
        "created": 0,
        "duplicates": 1,
        "linked": 1,
    }
    exported = client.get("/api/privacy/export").json()
    assert len(exported["transactions"]) == len(exported["import_marks"]) == 1
    assert client.get("/api/dashboard?month=2026-11").json() == before
    assert client.post(path, json=body).json()["linked"] == 1
    assert client.get("/api/privacy/export").json() == exported
    assert len(client.get("/api/history?entity=import_link").json()["items"]) == 1
    changed = client.put(
        "/api/transactions/" + row["id"], json=edit_body(row, amount_cents=2000)
    ).json()
    assert client.post(path, json=body).json()["created"] == 0
    assert (
        client.delete(
            f"/api/transactions/{row['id']}?expected_version={changed['version']}"
        ).status_code
        == 204
    )
    assert client.post(path, json={"content": CSV}).json() == {
        "created": 0,
        "duplicates": 1,
        "removed": 1,
    }
    login("bob")
    assert client.get("/api/history?entity=import_link").json()["items"] == []
    login()
    assert (
        client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        ).status_code
        == 200
    )
    login()
    assert all(not rows for rows in client.get("/api/privacy/export").json().values())


@pytest.mark.parametrize(
    "problem",
    ["version", "amount", "account", "owner", "index", "excluded", "duplicate"],
)
def test_invalid_or_changed_link_rolls_back_whole_batch(client, login, problem):
    login()
    a = account(client)
    row = client.post("/api/transactions", json=ENTRY).json()
    body = payload(row, CSV + "2026-11-04;Outra linha;5,00;despesa\n")
    if problem == "version":
        body["links"][0]["expected_version"] = 99
    elif problem == "amount":
        body["content"] = body["content"].replace("12,34", "12,35")
    elif problem == "account":
        body["account_id"] = a
    elif problem == "owner":
        login("bob")
    elif problem == "index":
        body["links"][0]["source_index"] = 4
    elif problem == "excluded":
        body["excluded_indices"] = [0]
    else:
        body["links"].append(dict(body["links"][0]))
    before = client.get("/api/privacy/export").json()
    response = client.post("/api/import/confirm", json=body)
    assert response.status_code in (409, 422), response.text
    assert client.get("/api/privacy/export").json() == before


def test_origin_cannot_be_reassigned_or_two_occurrences_collapsed(client, login):
    login()
    rows = [client.post("/api/transactions", json=ENTRY).json() for _ in range(2)]
    assert client.post("/api/import/confirm", json=payload(rows[0])).status_code == 200
    assert client.post("/api/import/confirm", json=payload(rows[1])).status_code == 409
    body = payload(rows[0], CSV + CSV.splitlines()[1] + "\n")
    body["links"].append({**body["links"][0], "source_index": 1})
    assert client.post("/api/import/confirm", json=body).status_code == 422


def test_card_link_stays_in_fatura_and_survives_operation_deletion(client, login):
    _, card = setup(client, login)
    purchase, _ = buy(
        client, card, date="2026-11-03", amount_cents=1234, installments=1
    )
    row = purchase.json()[0]
    bill = statement(client)
    path = f"/api/statements/{bill['id']}/import/confirm"
    assert client.post(path, json=payload(row)).json() == {
        "created": 0,
        "duplicates": 1,
        "linked": 1,
    }
    assert len(client.get("/api/privacy/export").json()["card_charges"]) == 1
    assert (
        delete_operation(
            client, "/api/card-operations/" + row["operation_id"]
        ).status_code
        == 204
    )
    assert client.post(path, json={"content": CSV}).json()["removed"] == 1


def test_history_failure_rolls_back_link(client, login):
    login()
    row = client.post("/api/transactions", json=ENTRY).json()
    before = client.get("/api/privacy/export").json()

    def fail(mapper, connection, target):
        if target.entity == "import_link":
            raise RuntimeError("histórico indisponível")

    event.listen(FinancialAudit, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="histórico indisponível"):
            client.post("/api/import/confirm", json=payload(row))
    finally:
        event.remove(FinancialAudit, "before_insert", fail)
    assert client.get("/api/privacy/export").json() == before
