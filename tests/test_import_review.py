from tests.test_finance import CSV, ENTRY
from tests.test_balances import account
from tests.test_cards import buy, statement


def test_csv_candidates_are_advisory_scoped_and_preview_does_not_write(client, login):
    login()
    a, b = account(client, "A"), account(client, "B")
    original = client.post("/api/transactions", json={**ENTRY, "account_id": a,
                           "description": "Descrição diferente <script>"}).json()
    before = client.get("/api/privacy/export").json()
    body = {"content": CSV, "account_id": a}
    result = client.post("/api/import/preview", json=body)
    assert result.status_code == 200, result.text
    signals = result.json()["possible_duplicates"]
    assert signals[0]["source_index"] == 0
    assert signals[0]["matches"][0]["id"] == original["id"]
    assert not signals[0]["more"]
    assert client.get("/api/privacy/export").json() == before
    for context in (None, b):
        assert client.post("/api/import/preview", json={**body, "account_id": context}).json()["possible_duplicates"] == []
    login("bob")
    assert client.post("/api/import/preview", json=body).status_code == 404
    assert client.post("/api/import/preview", json={"content": CSV}).json()["possible_duplicates"] == []
    login()
    # Coincidência não impede compra legítima; reenvio continua deduplicado.
    assert client.post("/api/import/confirm", json=body).json()["created"] == 1
    assert client.post("/api/import/confirm", json=body).json()["created"] == 0


def test_candidate_limit_and_kind_date_value_filters(client, login):
    login()
    for _ in range(7):
        assert client.post("/api/transactions", json=ENTRY).status_code == 201
    for changes in ({"kind": "income"}, {"date": "2026-11-04"}, {"amount_cents": 1235}):
        client.post("/api/transactions", json={**ENTRY, **changes})
    result = client.post("/api/import/preview", json={"content": CSV}).json()
    signal = result["possible_duplicates"][0]
    assert len(signal["matches"]) == 5 and signal["more"]
    assert all(row["kind"] == "expense" and row["date"] == "2026-11-03"
               and row["amount_cents"] == 1234 for row in signal["matches"])


def test_card_candidates_stay_in_selected_statement(client, login):
    login()
    card = client.post("/api/cards", json={"name": "A", "due_day": 10}).json()
    other = client.post("/api/cards", json={"name": "B", "due_day": 10}).json()
    buy(client, card, amount_cents=1234, installments=1, date="2026-11-03")
    bill = statement(client)
    path = f"/api/statements/{bill['id']}/import/preview"
    result = client.post(path, json={"content": CSV})
    assert result.status_code == 200, result.text
    assert len(result.json()["possible_duplicates"]) == 1
    buy(client, other, amount_cents=9999, installments=1)
    bills = client.get("/api/statements?month=2026-11").json()
    other_bill = next(row for row in bills if row["card_id"] == other["id"])
    assert client.post(f"/api/statements/{other_bill['id']}/import/preview", json={"content": CSV}).json()["possible_duplicates"] == []
    login("bob")
    assert client.post(path, json={"content": CSV}).status_code == 404
