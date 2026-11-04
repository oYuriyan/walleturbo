import pytest
from app.domain import Entry, parse_csv, import_keys, summarize

CSV = "data;descricao;valor;tipo\n2026-11-03;Mercado;12,34;despesa\n"
ENTRY = {
    "date": "2026-11-03",
    "description": "Mercado",
    "amount_cents": 1234,
    "kind": "expense",
    "category": "Alimentação",
    "reviewed": True,
}


def test_cents_and_totals():
    expense = Entry(**ENTRY)
    income = Entry(**{**ENTRY, "kind": "income", "amount_cents": 2000})
    assert summarize([expense, income])["balance_cents"] == 766
    with pytest.raises(ValueError):
        Entry(**{**ENTRY, "amount_cents": 12.34})


@pytest.mark.parametrize(
    "content",
    [
        "data,valor\n1,2",
        CSV.replace("12,34", "-12,34"),
        CSV.replace("12,34", "12.34"),
        CSV.replace("12,34", "NaN"),
        CSV.replace("2026-11-03", "2026-02-30"),
        CSV.replace("despesa", "transferencia"),
    ],
)
def test_invalid_csv(content):
    with pytest.raises(ValueError):
        parse_csv(content)


def test_import_keeps_identical_purchases():
    rows = parse_csv(CSV + "2026-11-03;Mercado;12,34;despesa\n")
    assert rows[0].amount_cents == 1234
    assert len(set(import_keys(rows))) == 2
    assert import_keys(rows) == import_keys(rows)


def test_import_limit():
    with pytest.raises(ValueError):
        parse_csv("data;descricao;valor;tipo\n" + "2026-11-03;X;1,00;despesa\n" * 501)


def test_create_review_month_and_delete(client, login):
    login()
    result = client.post("/api/transactions", json=ENTRY)
    assert result.status_code == 201
    row = result.json()
    assert client.get("/api/dashboard?month=2026-11").json()["expense_cents"] == 1234
    assert client.get("/api/dashboard?month=2026-12").json()["transactions"] == []
    assert (
        client.put(
            "/api/transactions/" + row["id"], json={**ENTRY, "category": "Outros"}
        ).json()["category"]
        == "Outros"
    )
    assert client.delete("/api/transactions/" + row["id"]).status_code == 204


def test_duplicate_import_atomic_validation(client, login):
    login()
    assert (
        client.post("/api/import/preview", json={"content": CSV}).json()["entries"][0][
            "category"
        ]
        == "Alimentação"
    )
    assert client.get("/api/dashboard?month=2026-11").json()["transactions"] == []
    assert client.post("/api/import/confirm", json={"content": CSV}).json() == {
        "created": 1,
        "duplicates": 0,
    }
    assert client.post("/api/import/confirm", json={"content": CSV}).json() == {
        "created": 0,
        "duplicates": 1,
    }
    assert (
        client.post(
            "/api/import/confirm", json={"content": CSV + "invalid\n"}
        ).status_code
        == 422
    )
    assert len(client.get("/api/dashboard?month=2026-11").json()["transactions"]) == 1


def test_goal_validation_and_update(client, login):
    login()
    goal = {
        "name": "Reserva",
        "target_cents": 50000,
        "saved_cents": 1000,
        "deadline": "2027-01-01",
    }
    result = client.post("/api/goals", json=goal)
    assert result.status_code == 201
    assert (
        client.put(
            "/api/goals/" + result.json()["id"],
            json={
                **goal,
                "saved_cents": 2000,
                "archived": False,
                "expected_version": 0,
            },
        ).json()["saved_cents"]
        == 2000
    )
    assert (
        client.post("/api/goals", json={**goal, "saved_cents": 60000}).status_code
        == 422
    )
