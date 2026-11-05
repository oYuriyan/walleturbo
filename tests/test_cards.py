from uuid import uuid4
import pytest
from app.cards import split_cents, due_date, shift_month
from tests.test_finance import ENTRY, CSV


def setup(client, login, day=10):
    login()
    account = client.post("/api/accounts", json={"name": "Principal"}).json()
    card = client.post("/api/cards", json={"name": "Meu cartão", "due_day": day}).json()
    return account, card


def buy(client, card, **overrides):
    body = {
        "request_id": str(uuid4()),
        "card_id": card["id"],
        "first_month": "2026-11",
        "date": "2026-10-28",
        "description": "Notebook",
        "amount_cents": 10001,
        "installments": 3,
        "kind": "expense",
        "category": "Compras",
        "reviewed": True,
        **overrides,
    }
    return client.post("/api/card-purchases", json=body), body


def statement(client, month="2026-11"):
    return client.get("/api/statements?month=" + month).json()[0]


def delete_operation(client, path):
    response = client.get(path)
    revision = response.json()["revision"] if response.status_code == 200 else "0" * 64
    return client.delete(path + "?expected_revision=" + revision)


def test_installment_rounding_and_calendar():
    assert split_cents(10001, 3) == [3334, 3334, 3333]
    assert sum(split_cents(99999999999, 36)) == 99999999999
    assert due_date("2028-02", 31).isoformat() == "2028-02-29"
    assert due_date("2027-02", 31).isoformat() == "2027-02-28"
    assert shift_month("2026-12", 1) == "2027-01"


def test_installments_months_and_idempotency(client, login):
    account, card = setup(client, login, 31)
    response, body = buy(client, card)
    assert response.status_code == 201
    assert [c["amount_cents"] for c in response.json()] == [3334, 3334, 3333]
    assert statement(client, "2027-01")["total_cents"] == 3333
    assert statement(client)["due_date"] == "2026-11-30"
    assert client.post("/api/card-purchases", json=body).json() == response.json()
    assert statement(client)["total_cents"] == 3334
    assert (
        client.post(
            "/api/card-purchases", json={**body, "amount_cents": 10002}
        ).status_code
        == 409
    )
    assert client.get("/api/dashboard?month=2026-11").json()["expense_cents"] == 3334


def test_reconciliation_and_payment_do_not_double_expenses(client, login):
    account, card = setup(client, login)
    buy(client, card, amount_cents=10000, installments=1)
    s = statement(client)
    payment = {
        "request_id": str(uuid4()),
        "account_id": account["id"],
        "date": "2026-11-10",
        "amount_cents": 6000,
    }
    assert (
        client.post(f"/api/statements/{s['id']}/payments", json=payment).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/statements/{s['id']}/close", json={"expected_cents": 9999}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/statements/{s['id']}/close", json={"expected_cents": 10000}
        ).status_code
        == 200
    )
    response = client.post(f"/api/statements/{s['id']}/payments", json=payment)
    assert response.status_code == 201
    assert (
        client.post(f"/api/statements/{s['id']}/payments", json=payment).json()
        == response.json()
    )
    assert (
        client.post(
            f"/api/statements/{s['id']}/payments",
            json={**payment, "amount_cents": 1000},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/statements/{s['id']}/payments",
            json={**payment, "request_id": str(uuid4()), "amount_cents": 4001},
        ).status_code
        == 409
    )
    data = client.get("/api/dashboard?month=2026-11").json()
    assert data["expense_cents"] == 10000
    assert data["cash_balance_cents"] == -6000
    assert data["balance_cents"] == -10000
    assert statement(client)["remaining_cents"] == 4000
    assert client.post(f"/api/statements/{s['id']}/reopen").status_code == 409
    assert (
        client.delete(
            "/api/statement-payments/"
            + response.json()["id"]
            + "?expected_version="
            + str(response.json()["version"])
        ).status_code
        == 204
    )
    assert client.post(f"/api/statements/{s['id']}/reopen").status_code == 200


def test_refund_reduces_consumption_and_full_payment(client, login):
    account, card = setup(client, login)
    buy(client, card, installments=1, amount_cents=10000)
    buy(client, card, kind="refund", installments=1, amount_cents=2500)
    s = statement(client)
    assert s["total_cents"] == 7500
    assert client.get("/api/dashboard?month=2026-11").json()["expense_cents"] == 7500
    client.post(f"/api/statements/{s['id']}/close", json={"expected_cents": 7500})
    assert (
        client.post(
            f"/api/statements/{s['id']}/payments",
            json={
                "request_id": str(uuid4()),
                "account_id": account["id"],
                "date": "2026-12-01",
                "amount_cents": 7500,
            },
        ).status_code
        == 201
    )
    assert statement(client)["remaining_cents"] == 0
    assert client.get("/api/dashboard?month=2026-11").json()["cash_balance_cents"] == 0
    assert (
        client.get("/api/dashboard?month=2026-12").json()["cash_balance_cents"] == -7500
    )
    assert client.get("/api/dashboard?month=2026-12").json()["expense_cents"] == 0


def test_pending_review_blocks_close_and_closed_bill_is_immutable(client, login):
    _, card = setup(client, login)
    response, _ = buy(client, card, installments=1, reviewed=False)
    charge = response.json()[0]
    s = statement(client)
    assert (
        client.post(
            f"/api/statements/{s['id']}/close", json={"expected_cents": 10001}
        ).status_code
        == 409
    )
    assert (
        client.put(
            f"/api/card-charges/{charge['id']}/review",
            json={
                "category": "Educação",
                "reviewed": True,
                "expected_version": charge["version"],
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/statements/{s['id']}/close", json={"expected_cents": 10001}
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/card-charges/{charge['id']}/review",
            json={
                "category": "Compras",
                "reviewed": True,
                "expected_version": charge["version"],
            },
        ).status_code
        == 409
    )
    assert (
        delete_operation(
            client, "/api/card-operations/" + charge["operation_id"]
        ).status_code
        == 409
    )
    assert buy(client, card, installments=1)[0].status_code == 409


def test_batch_rolls_back_if_a_future_statement_is_closed(client, login):
    _, card = setup(client, login)
    s = client.post(f"/api/cards/{card['id']}/statements?month=2026-12").json()
    client.post(f"/api/statements/{s['id']}/close", json={"expected_cents": 0})
    assert buy(client, card)[0].status_code == 409
    assert client.get("/api/statements?month=2026-11").json() == []
    assert client.get("/api/privacy/export").json()["card_charges"] == []


def test_operation_delete_is_atomic_across_installments(client, login):
    _, card = setup(client, login)
    response, _ = buy(client, card)
    s = statement(client, "2026-12")
    client.post(f"/api/statements/{s['id']}/close", json={"expected_cents": 3334})
    assert (
        delete_operation(
            client, "/api/card-operations/" + response.json()[0]["operation_id"]
        ).status_code
        == 409
    )
    assert len(client.get("/api/privacy/export").json()["card_charges"]) == 3
    client.post(f"/api/statements/{s['id']}/reopen")
    assert (
        delete_operation(
            client, "/api/card-operations/" + response.json()[0]["operation_id"]
        ).status_code
        == 204
    )
    assert client.get("/api/privacy/export").json()["card_charges"] == []


def test_statement_csv_scopes_duplicates_and_requires_review(client, login):
    _, card = setup(client, login)
    second = client.post("/api/cards", json={"name": "Outro", "due_day": 20}).json()
    a = client.post(f"/api/cards/{card['id']}/statements?month=2026-11").json()
    b = client.post(f"/api/cards/{second['id']}/statements?month=2026-11").json()
    body = {"content": CSV}
    path = f"/api/statements/{a['id']}/import/"
    assert client.post(path + "preview", json=body).status_code == 200
    assert statement(client)["total_cents"] == 0
    assert client.post(path + "confirm", json=body).json() == {
        "created": 1,
        "duplicates": 0,
    }
    assert client.post(path + "confirm", json=body).json() == {
        "created": 0,
        "duplicates": 1,
    }
    assert client.post(
        f"/api/statements/{b['id']}/import/confirm", json=body
    ).json() == {"created": 1, "duplicates": 0}
    assert (
        client.post(
            path + "confirm", json={"content": CSV.replace("despesa", "receita")}
        ).status_code
        == 422
    )
    assert statement(client)["pending"] == 1


def test_account_owner_checked_and_import_scoped(client, login):
    account, card = setup(client, login)
    second = client.post("/api/accounts", json={"name": "Outra"}).json()
    assert (
        client.post(
            "/api/import/confirm", json={"content": CSV, "account_id": account["id"]}
        ).json()["created"]
        == 1
    )
    assert (
        client.post(
            "/api/import/confirm", json={"content": CSV, "account_id": second["id"]}
        ).json()["created"]
        == 1
    )
    login("bob")
    assert (
        client.post(
            "/api/transactions", json={**ENTRY, "account_id": account["id"]}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/import/confirm", json={"content": CSV, "account_id": account["id"]}
        ).status_code
        == 404
    )
    assert client.get("/api/cards").json() == []
    assert client.get("/api/accounts").json() == []
    assert buy(client, card)[0].status_code == 404


def test_all_statement_routes_enforce_owner(client, login):
    account, card = setup(client, login)
    response, _ = buy(client, card, installments=1)
    charge = response.json()[0]
    s = statement(client)
    client.post(f"/api/statements/{s['id']}/close", json={"expected_cents": 10001})
    payment = {
        "request_id": str(uuid4()),
        "account_id": account["id"],
        "date": "2026-11-10",
        "amount_cents": 10001,
    }
    p = client.post(f"/api/statements/{s['id']}/payments", json=payment).json()
    login("bob")
    assert client.get("/api/statements?month=2026-11").json() == []
    assert (
        client.post(f"/api/statements/{s['id']}/payments", json=payment).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/statements/{s['id']}/close", json={"expected_cents": 10001}
        ).status_code
        == 404
    )
    assert client.post(f"/api/statements/{s['id']}/reopen").status_code == 404
    assert (
        client.post(
            f"/api/statements/{s['id']}/import/preview", json={"content": CSV}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/statements/{s['id']}/import/confirm", json={"content": CSV}
        ).status_code
        == 404
    )
    assert (
        client.delete(
            "/api/statement-payments/"
            + p["id"]
            + "?expected_version="
            + str(p["version"])
        ).status_code
        == 404
    )
    assert (
        delete_operation(
            client, "/api/card-operations/" + charge["operation_id"]
        ).status_code
        == 404
    )
    assert (
        client.put(
            "/api/card-charges/" + charge["id"] + "/review",
            json={
                "category": "Compras",
                "reviewed": True,
                "expected_version": charge["version"],
            },
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "change",
    [
        {"installments": 37},
        {"installments": 2, "amount_cents": 1},
        {"kind": "refund", "installments": 2},
        {"first_month": "2026-13"},
        {"first_month": "9999-12", "installments": 2},
        {"amount_cents": True},
        {"category": "Renda"},
    ],
)
def test_invalid_purchases(client, login, change):
    _, card = setup(client, login)
    assert buy(client, card, **change)[0].status_code == 422


def test_export_and_erase_include_new_records(client, login):
    _, card = setup(client, login)
    buy(client, card)
    data = client.get("/api/privacy/export").json()
    assert (
        len(data["cards"]) == 1
        and len(data["card_charges"]) == 3
        and len(data["statements"]) == 3
    )
    assert all(
        "owner" not in row and "payload_hash" not in row for row in data["card_charges"]
    )
    assert (
        client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        ).status_code
        == 200
    )
    login()
    assert all(not rows for rows in client.get("/api/privacy/export").json().values())
