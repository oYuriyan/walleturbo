from datetime import date
from types import SimpleNamespace
from app.planning import goal_plan
from tests.test_cards import setup, buy, statement
from tests.test_finance import ENTRY


def add(
    client,
    amount,
    kind="expense",
    category="Compras",
    when="2026-11-01",
    description="Compra",
):
    return client.post(
        "/api/transactions",
        json={
            **ENTRY,
            "amount_cents": amount,
            "kind": kind,
            "category": category,
            "date": when,
            "description": description,
        },
    )


def test_allocation_never_exceeds_capacity_and_deadline_order():
    goals = [
        SimpleNamespace(
            id="b",
            name="B",
            deadline=date(2027, 3, 1),
            target_cents=9000,
            saved_cents=0,
        ),
        SimpleNamespace(
            id="a",
            name="A",
            deadline=date(2027, 1, 31),
            target_cents=1000,
            saved_cents=0,
        ),
    ]
    result = goal_plan(goals, 1500, date(2027, 1, 1))
    assert [g["id"] for g in result] == ["a", "b"]
    assert [g["suggested_cents"] for g in result] == [1000, 500]
    assert sum(g["suggested_cents"] for g in result) <= 1500
    assert all(
        g["suggested_cents"] is None for g in goal_plan(goals, None, date(2027, 1, 1))
    )
    assert goal_plan(goals, 10000, date(2027, 4, 1))[0]["expired"]
    assert all(
        g["suggested_cents"] == 0 for g in goal_plan(goals, 10000, date(2027, 4, 1))
    )


def test_no_capacity_until_complete_and_reviewed(client, login):
    login()
    add(client, 10000, "income", "Renda")
    add(client, 2000)
    assert client.get("/api/planning/2026-11").json()["capacity_cents"] is None
    assert (
        client.put(
            "/api/planning/2026-11/plan",
            json={
                **({"records_complete": True, "buffer_cents": 1000}),
                "expected_version": client.get(
                    ("/api/planning/2026-11/plan").rsplit("/", 1)[0]
                ).json()["version"],
            },
        ).status_code
        == 200
    )
    data = client.get("/api/planning/2026-11").json()
    assert data["capacity_cents"] == 7000
    add(client, 1000)
    data = client.get("/api/planning/2026-11").json()
    assert data["capacity_cents"] is None and not data["plan"]["records_complete"]


def test_reference_income_cannot_inflate_result_and_cash(client, login):
    account, card = setup(client, login)
    add(client, 10000, "income", "Renda")
    buy(client, card, installments=1, amount_cents=4000)
    client.put(
        "/api/planning/2026-11/plan",
        json={
            **(
                {
                    "records_complete": True,
                    "income_reference_cents": 100000,
                    "buffer_cents": 1000,
                }
            ),
            "expected_version": client.get(
                ("/api/planning/2026-11/plan").rsplit("/", 1)[0]
            ).json()["version"],
        },
    )
    data = client.get("/api/planning/2026-11").json()
    assert data["capacity_cents"] == 5000 and data["figures"]["expense_cents"] == 4000
    assert data["figures"]["cash_change_cents"] == 10000
    client.put(
        "/api/planning/2026-11/plan",
        json={
            **({"records_complete": True, "income_reference_cents": 3000}),
            "expected_version": client.get(
                ("/api/planning/2026-11/plan").rsplit("/", 1)[0]
            ).json()["version"],
        },
    )
    assert client.get("/api/planning/2026-11").json()["capacity_cents"] == 0


def test_expected_income_without_actual_income_cannot_fund_goals(client, login):
    login()
    client.put(
        "/api/planning/2026-11/plan",
        json={
            **({"records_complete": True, "income_reference_cents": 100000}),
            "expected_version": client.get(
                ("/api/planning/2026-11/plan").rsplit("/", 1)[0]
            ).json()["version"],
        },
    )
    assert client.get("/api/planning/2026-11").json()["capacity_cents"] is None


def test_budgets_include_refunds_and_payments_do_not_duplicate(client, login):
    _, card = setup(client, login)
    add(client, 5000)
    buy(client, card, installments=1, amount_cents=4000)
    buy(client, card, installments=1, amount_cents=1000, kind="refund")
    assert (
        client.put(
            "/api/planning/2026-11/budget",
            json={
                **({"category": "Compras", "amount_cents": 7000}),
                "expected_version": client.get(
                    ("/api/planning/2026-11/budget").rsplit("/", 1)[0]
                ).json()["version"],
            },
        ).status_code
        == 200
    )
    data = client.get("/api/planning/2026-11").json()
    assert (
        data["budgets"][0]["spent_cents"] == 8000
        and data["budgets"][0]["exceeded_cents"] == 1000
    )
    assert (
        client.delete(
            (
                "/api/planning/2026-11/budget/Compras"
                + "?expected_version="
                + str(
                    client.get(
                        ("/api/planning/2026-11/budget/Compras").split("/budget/")[0]
                    ).json()["version"]
                )
            )
        ).status_code
        == 204
    )
    assert (
        client.delete(
            (
                "/api/planning/2026-11/budget/Compras"
                + "?expected_version="
                + str(
                    client.get(
                        ("/api/planning/2026-11/budget/Compras").split("/budget/")[0]
                    ).json()["version"]
                )
            )
        ).status_code
        == 404
    )


def test_recurrence_requires_distinct_months_and_excludes_installments(client, login):
    _, card = setup(client, login)
    for month in ("09", "10", "11"):
        add(
            client,
            2000,
            category="Assinaturas",
            when=f"2026-{month}-01",
            description="Streaming",
        )
    for _ in range(3):
        add(client, 1000, category="Assinaturas", description="Compra repetida")
    buy(
        client,
        card,
        installments=3,
        first_month="2026-09",
        category="Assinaturas",
        description="Serviço parcelado",
    )
    data = client.get("/api/planning/2026-11").json()
    assert (
        len(data["recurrences"]) == 1
        and data["recurrences"][0]["merchant"] == "Streaming"
    )
    assert data["recurrences"][0]["months"] == ["2026-09", "2026-10", "2026-11"]
    assert len(data["recurrences"][0]["evidence"]) == 3


def test_planning_owner_isolation_and_privacy(client, login):
    login()
    client.put(
        "/api/planning/2026-11/budget",
        json={
            **({"category": "Compras", "amount_cents": 7000}),
            "expected_version": client.get(
                ("/api/planning/2026-11/budget").rsplit("/", 1)[0]
            ).json()["version"],
        },
    )
    client.put(
        "/api/planning/2026-11/plan",
        json={
            **({"buffer_cents": 500}),
            "expected_version": client.get(
                ("/api/planning/2026-11/plan").rsplit("/", 1)[0]
            ).json()["version"],
        },
    )
    login("bob")
    assert client.get("/api/planning/2026-11").json()["budgets"] == []
    assert (
        client.delete(
            (
                "/api/planning/2026-11/budget/Compras"
                + "?expected_version="
                + str(
                    client.get(
                        ("/api/planning/2026-11/budget/Compras").split("/budget/")[0]
                    ).json()["version"]
                )
            )
        ).status_code
        == 404
    )
    assert client.get("/api/privacy/export").json()["month_plans"] == []
    login()
    assert len(client.get("/api/privacy/export").json()["budgets"]) == 1
    assert (
        client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        ).status_code
        == 200
    )
    login()
    assert client.get("/api/privacy/export").json()["month_plans"] == []


def test_invalid_parameters_and_auth(client, login):
    assert client.get("/api/planning/2026-11").status_code == 401
    login()
    for month in ("invalid", "9999-12", "0000-01", "2026-13"):
        assert client.get("/api/planning/" + month).status_code == 422
    assert (
        client.put(
            "/api/planning/2026-11/budget",
            json={
                **({"category": "Renda", "amount_cents": 1000}),
                "expected_version": client.get(
                    ("/api/planning/2026-11/budget").rsplit("/", 1)[0]
                ).json()["version"],
            },
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/planning/2026-11/plan",
            json={
                **({"buffer_cents": -1}),
                "expected_version": client.get(
                    ("/api/planning/2026-11/plan").rsplit("/", 1)[0]
                ).json()["version"],
            },
        ).status_code
        == 422
    )
