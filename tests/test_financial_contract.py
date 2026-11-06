"""Exemplo público de DOMINIO_FINANCEIRO.md, com resultados independentes."""

from uuid import uuid4

import pytest

from tests.test_balances import account, balances, opening, transfer
from tests.test_cards import buy, statement
from tests.test_finance import ENTRY
from tests.test_payment_corrections import body as correction_body


@pytest.mark.parametrize("correct_payment", [False, True])
def test_three_month_contract_across_reports(client, login, correct_payment):
    login()
    a, b = account(client, "A"), account(client, "B")
    assert opening(client, a, amount_cents=10000)[0].status_code == 200
    assert opening(client, b, amount_cents=500)[0].status_code == 200
    for values in ({"kind": "income", "category": "Renda", "amount_cents": 50000}, {}):
        response = client.post("/api/transactions", json={**ENTRY, "account_id": a, **values})
        assert response.status_code == 201, response.text
    card = client.post("/api/cards", json={"name": "Cartão", "due_day": 10}).json()
    purchase, purchase_body = buy(client, card)
    assert purchase.status_code == 201
    assert client.post("/api/card-purchases", json=purchase_body).json() == purchase.json()
    assert buy(client, card, amount_cents=334, installments=1, kind="refund")[0].status_code == 201
    bill = statement(client)
    path = f"/api/statements/{bill['id']}"
    closed = client.post(path + "/close", json={
        "expected_cents": 3000,
        "expected_revision": client.get(path).json()["revision"],
    })
    assert closed.status_code == 200, closed.text
    payment_body = {"request_id": str(uuid4()), "account_id": a,
                    "date": "2026-11-10", "amount_cents": 2000}
    payment = client.post(path + "/payments", json=payment_body)
    assert payment.status_code == 201, payment.text
    assert client.post(path + "/payments", json=payment_body).json() == payment.json()
    moved, transfer_body = transfer(client, a, b, amount_cents=5000)
    assert moved.status_code == 201
    reverse = f"/api/transfers/{moved.json()['id']}/reverse"
    assert client.post(reverse, json={"date": "2026-12-02"}).status_code == 200
    assert client.post(reverse, json={"date": "2026-12-02"}).status_code == 200
    assert client.post("/api/transfers", json=transfer_body).json()["id"] == moved.json()["id"]

    if correct_payment:
        change = correction_body(payment.json(), account_id=b, date="2026-12-03")
        edit_path = "/api/statement-payments/" + payment.json()["id"]
        response = client.put(edit_path, json=change)
        assert response.status_code == 200, response.text
        assert client.put(edit_path, json=change).json() == response.json()

    # Valores calculados à mão; não reutilizar funções de cálculo da aplicação.
    november_cash = 48766 if correct_payment else 46766
    december_cash = -2000 if correct_payment else 0
    expected = [
        ("2026-11", "2026-11-30", 50000, 4234, 45766, november_cash,
         (53766 if correct_payment else 51766, 5500)),
        ("2026-12", "2026-12-31", 0, 3334, -3334, december_cash,
         (58766, -1500) if correct_payment else (56766, 500)),
        ("2027-01", "2027-01-31", 0, 3333, -3333, 0,
         (58766, -1500) if correct_payment else (56766, 500)),
    ]
    cumulative_cash = 0
    for month, day, income, expense, result, cash, account_values in expected:
        dashboard = client.get("/api/dashboard?month=" + month).json()
        figures = client.get("/api/planning/" + month).json()["figures"]
        assert (dashboard["income_cents"], dashboard["expense_cents"],
                dashboard["balance_cents"], dashboard["cash_balance_cents"]) == (income, expense, result, cash)
        assert (figures["income_cents"], figures["expense_cents"],
                figures["result_cents"], figures["cash_change_cents"]) == (income, expense, result, cash)
        report = balances(client, day)
        by_id = {row["id"]: row["balance_cents"] for row in report["accounts"]}
        assert (by_id[a], by_id[b]) == account_values
        cumulative_cash += cash
        assert report["total_cents"] == 10500 + cumulative_cash
    assert statement(client)["remaining_cents"] == 1000
