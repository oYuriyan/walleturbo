import pytest
from tests.test_finance import CSV
from tests.test_cards import setup, statement


@pytest.mark.parametrize("card_mode", [False, True])
def test_selection_preserves_occurrences_and_can_import_ignored_later(client, login, card_mode):
    _, card = setup(client, login)
    if card_mode:
        bill = client.post(f"/api/cards/{card['id']}/statements?month=2026-11")
        assert bill.status_code in (200, 201), bill.text
        path = f"/api/statements/{statement(client)['id']}/import/confirm"
        entity = "card_charges"
    else:
        path, entity = "/api/import/confirm", "transactions"
    repeated = CSV + CSV.splitlines()[1] + "\n"
    body = {"content": repeated, "excluded_indices": [0]}
    assert client.post(path, json=body).json() == {"created": 1, "duplicates": 0, "skipped": 1}
    first = client.get("/api/privacy/export").json()
    assert len(first[entity]) == 1 and len(first["import_marks"]) == 1
    assert client.post(path, json=body).json() == {"created": 0, "duplicates": 1, "skipped": 1}
    assert client.get("/api/privacy/export").json() == first
    assert client.post(path, json={"content": repeated}).json() == {"created": 1, "duplicates": 1}
    assert len(client.get("/api/privacy/export").json()[entity]) == 2


@pytest.mark.parametrize("excluded", [[0], [1], [-1], [True], [0.0], ["0"], [0, 0], [500]])
def test_invalid_selection_does_not_write(client, login, excluded):
    login()
    before = client.get("/api/privacy/export").json()
    response = client.post("/api/import/confirm", json={"content": CSV, "excluded_indices": excluded})
    assert response.status_code == 422, response.text
    assert client.get("/api/privacy/export").json() == before
