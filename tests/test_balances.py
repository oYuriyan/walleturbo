from uuid import uuid4
import pytest
from tests.test_finance import ENTRY
from tests.test_cards import buy, statement


def account(client, name="Conta"):
    return client.post("/api/accounts", json={"name": name}).json()["id"]


def opening(client, account_id, **changes):
    body = {
        "request_id": str(uuid4()),
        "date": "2026-11-01",
        "amount_cents": 10000,
        "expected_version": 0,
        "reason": "Saldo ao iniciar acompanhamento",
        **changes,
    }
    return client.put(f"/api/accounts/{account_id}/opening", json=body), body


def transfer(client, a, b, **changes):
    body = {
        "request_id": str(uuid4()),
        "source_account_id": a,
        "destination_account_id": b,
        "date": "2026-11-03",
        "amount_cents": 1234,
        "description": "Reserva",
        **changes,
    }
    return client.post("/api/transfers", json=body), body


def balances(client, day="2026-11-30"):
    response = client.get("/api/balances?as_of=" + day)
    assert response.status_code == 200, response.text
    return response.json()


def test_unknown_reference_and_unassigned_are_not_zero(client, login):
    login()
    assert balances(client)["total_cents"] is None
    a = account(client)
    report = balances(client)
    assert report["accounts"][0]["balance_cents"] is None
    assert report["unknown_accounts"] == 1
    opening(client, a, amount_cents=0)
    assert balances(client)["total_cents"] == 0
    client.post("/api/transactions", json=ENTRY)
    report = balances(client)
    assert report["total_cents"] is None and report["unassigned_transactions"] == 1
    assert report["known_subtotal_cents"] == 0


def test_reference_start_of_day_signed_balances_and_future(client, login):
    login()
    a = account(client)
    opening(client, a, amount_cents=-100)
    for day, amount in [("2026-10-31", 9000), ("2026-11-01", 100), ("2026-11-02", 200)]:
        assert (
            client.post(
                "/api/transactions",
                json={**ENTRY, "account_id": a, "date": day, "amount_cents": amount},
            ).status_code
            == 201
        )
    report = balances(client, "2026-11-01")
    assert report["total_cents"] == -200
    assert report["accounts"][0]["excluded_movements"] == 1
    assert balances(client, "2026-10-31")["accounts"][0]["status"] == "before_reference"
    assert balances(client)["total_cents"] == -400
    assert client.get("/api/dashboard?month=2026-11").json()["expense_cents"] == 300


def test_opening_correction_keeps_history_and_detects_conflict(client, login):
    login()
    a = account(client)
    first, body = opening(client, a)
    assert first.status_code == 200
    second, _ = opening(
        client, a, expected_version=1, amount_cents=20000, reason="Corrigir leitura"
    )
    assert second.json()["version"] == 2
    assert client.put(f"/api/accounts/{a}/opening", json=body).json() == first.json()
    assert opening(client, a)[0].status_code == 409
    assert (
        client.put(
            f"/api/accounts/{a}/opening", json={**body, "amount_cents": 1}
        ).status_code
        == 409
    )
    assert balances(client)["total_cents"] == 20000
    assert len(client.get("/api/privacy/export").json()["opening_balances"]) == 2


def test_transfer_reversal_is_dated_persistent_and_neutral(client, login):
    login()
    a, b = account(client, "A"), account(client, "B")
    opening(client, a)
    opening(client, b, amount_cents=0)
    response, body = transfer(client, a, b)
    assert response.status_code == 201
    path = "/api/transfers/" + response.json()["id"] + "/reverse"
    assert [r["balance_cents"] for r in balances(client)["accounts"]] == [8766, 1234]
    assert balances(client)["total_cents"] == 10000
    for field in (
        "income_cents",
        "expense_cents",
        "balance_cents",
        "cash_balance_cents",
    ):
        assert client.get("/api/dashboard?month=2026-11").json()[field] == 0
    assert client.post(path, json={"date": "2026-11-02"}).status_code == 422
    assert client.post(path, json={"date": "2026-11-04"}).status_code == 200
    assert client.post(path, json={"date": "2026-11-04"}).status_code == 200
    assert client.post(path, json={"date": "2026-11-05"}).status_code == 409
    assert [r["balance_cents"] for r in balances(client, "2026-11-03")["accounts"]] == [
        8766,
        1234,
    ]
    assert [r["balance_cents"] for r in balances(client)["accounts"]] == [10000, 0]
    assert (
        client.post("/api/transfers", json=body).json()["reversed_date"] == "2026-11-04"
    )
    assert (
        client.post("/api/transfers", json={**body, "amount_cents": 1}).status_code
        == 409
    )
    assert len(client.get("/api/transfers").json()["items"]) == 1


def test_card_only_payment_affects_account_and_reversal_restores_it(client, login):
    login()
    a = account(client)
    opening(client, a)
    card = client.post("/api/cards", json={"name": "Cartão", "due_day": 10}).json()
    buy(client, card, amount_cents=8000, installments=1)
    assert balances(client)["total_cents"] == 10000
    s = statement(client)
    client.post(f"/api/statements/{s['id']}/close", json={"expected_cents": 8000})
    payment = client.post(
        f"/api/statements/{s['id']}/payments",
        json={
            "request_id": str(uuid4()),
            "account_id": a,
            "date": "2026-11-10",
            "amount_cents": 3000,
        },
    )
    assert payment.status_code == 201
    assert balances(client)["total_cents"] == 7000
    client.delete("/api/statement-payments/" + payment.json()["id"])
    assert balances(client)["total_cents"] == 10000


def test_isolation_and_privacy_include_all_balance_records(client, login):
    login()
    a, b = account(client), account(client)
    opening(client, a)
    tr, _ = transfer(client, a, b)
    login("bob")
    c = account(client)
    assert opening(client, a)[0].status_code == 404
    assert transfer(client, c, a)[0].status_code == 404
    assert (
        client.post(
            "/api/transfers/" + tr.json()["id"] + "/reverse",
            json={"date": "2026-11-04"},
        ).status_code
        == 404
    )
    assert client.get("/api/transfers").json()["items"] == []
    assert len(balances(client)["accounts"]) == 1
    login()
    export = client.get("/api/privacy/export").json()
    assert len(export["transfers"]) == len(export["opening_balances"]) == 1
    assert (
        "owner" not in export["transfers"][0]
        and "payload_hash" not in export["transfers"][0]
    )
    assert (
        client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        ).status_code
        == 200
    )
    login()
    assert all(not rows for rows in client.get("/api/privacy/export").json().values())
    login("bob")
    assert len(balances(client)["accounts"]) == 1


@pytest.mark.parametrize("amount", [0, -1, True, 1.5, 100000000000])
def test_invalid_transfer_amount(client, login, amount):
    login()
    a, b = account(client), account(client)
    assert transfer(client, a, b, amount_cents=amount)[0].status_code == 422


def test_same_account_and_pagination(client, login):
    login()
    a, b = account(client), account(client)
    assert transfer(client, a, a)[0].status_code == 422
    transfer(client, a, b)
    transfer(client, b, a)
    assert client.get("/api/transfers?limit=1").json()["has_more"]
    assert not client.get("/api/transfers?limit=1&offset=1").json()["has_more"]


def test_complete_cash_scenario_conserves_total_without_double_expense(client, login):
    login()
    a, b = account(client, "A"), account(client, "B")
    opening(client, a, amount_cents=10000)
    opening(client, b, amount_cents=500)
    assert (
        client.post(
            "/api/transactions",
            json={
                **ENTRY,
                "account_id": a,
                "kind": "income",
                "category": "Renda",
                "amount_cents": 5000,
            },
        ).status_code
        == 201
    )
    assert (
        client.post("/api/transactions", json={**ENTRY, "account_id": a}).status_code
        == 201
    )
    card = client.post("/api/cards", json={"name": "Cartão", "due_day": 10}).json()
    buy(client, card, amount_cents=8000, installments=1)
    bill = statement(client)
    client.post(f"/api/statements/{bill['id']}/close", json={"expected_cents": 8000})
    client.post(
        f"/api/statements/{bill['id']}/payments",
        json={
            "request_id": str(uuid4()),
            "account_id": a,
            "date": "2026-11-10",
            "amount_cents": 2500,
        },
    )
    tr, _ = transfer(client, a, b, amount_cents=2000)
    report = balances(client)
    assert [row["balance_cents"] for row in report["accounts"]] == [9266, 2500]
    assert report["total_cents"] == 11766
    dashboard = client.get("/api/dashboard?month=2026-11").json()
    assert dashboard["income_cents"] == 5000
    assert dashboard["expense_cents"] == 9234
    assert dashboard["balance_cents"] == -4234
    assert dashboard["cash_balance_cents"] == 1266
    assert report["total_cents"] == 10500 + dashboard["cash_balance_cents"]
    client.post(
        f"/api/transfers/{tr.json()['id']}/reverse", json={"date": "2026-11-20"}
    )
    assert [row["balance_cents"] for row in balances(client)["accounts"]] == [
        11266,
        500,
    ]
    assert balances(client)["total_cents"] == 11766
