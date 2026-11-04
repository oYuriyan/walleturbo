import pytest
from datetime import date
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.db import Account, FinancialAudit, Transaction, db_session
from app.main import app
from tests.test_finance import ENTRY
from tests.test_balances import account, opening, transfer
from tests.test_cards import buy, statement


def events(client, **params):
    r = client.get("/api/history", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_transaction_changes_and_deletion_keep_private_history(client, login):
    login()
    row = client.post("/api/transactions", json=ENTRY).json()
    client.put("/api/transactions/" + row["id"], json={**ENTRY, "amount_cents": 2000})
    # Mesmo conteúdo não produz mudança fictícia.
    client.put("/api/transactions/" + row["id"], json={**ENTRY, "amount_cents": 2000})
    client.delete("/api/transactions/" + row["id"])
    data = events(client, entity="transaction", entity_id=row["id"])["items"]
    assert [e["action"] for e in data] == ["deleted", "updated", "created"]
    assert data[1]["before"]["amount_cents"] == 1234
    assert data[1]["after"]["amount_cents"] == 2000
    assert data[0]["after"] is None and data[0]["before"]["amount_cents"] == 2000
    assert data[2]["before"] is None and data[2]["after"]["date"] == ENTRY["date"]
    assert all(
        "owner" not in e and "owner" not in (e["before"] or e["after"]) for e in data
    )
    assert len(client.get("/api/privacy/export").json()["financial_history"]) == 3


def test_import_replays_and_reversals_do_not_duplicate_history(client, login):
    login()
    a, b = account(client, "A"), account(client, "B")
    r, body = opening(client, a)
    client.put(f"/api/accounts/{a}/opening", json=body)
    r, body = transfer(client, a, b)
    client.post("/api/transfers", json=body)
    path = "/api/transfers/" + r.json()["id"] + "/reverse"
    client.post(path, json={"date": "2026-11-04"})
    client.post(path, json={"date": "2026-11-04"})
    assert len(events(client, entity="opening_balance")["items"]) == 1
    data = events(client, entity="transfer")["items"]
    assert len(data) == 2 and data[0]["before"]["reversed_date"] is None
    assert data[0]["after"]["reversed_date"] == "2026-11-04"
    assert "payload_hash" not in data[0]["after"]
    csv = {"content": "data;descricao;valor;tipo\n2026-11-03;Mercado;12,34;despesa\n"}
    client.post("/api/import/confirm", json=csv)
    client.post("/api/import/confirm", json=csv)
    data = events(client, entity="transaction")["items"]
    assert len(data) == 1 and "import_key" not in data[0]["after"]


def test_card_reconciliation_payment_and_reversal_have_history(client, login):
    login()
    a = account(client)
    c = client.post("/api/cards", json={"name": "Cartão", "due_day": 10}).json()
    buy(client, c, installments=1)
    s = statement(client)
    client.post(f"/api/statements/{s['id']}/close", json={"expected_cents": 10001})
    from uuid import uuid4

    p = client.post(
        f"/api/statements/{s['id']}/payments",
        json={
            "request_id": str(uuid4()),
            "account_id": a,
            "date": "2026-11-03",
            "amount_cents": 100,
        },
    ).json()
    client.delete("/api/statement-payments/" + p["id"])
    data = events(client, entity="statement_payment")["items"]
    assert [e["action"] for e in data] == ["deleted", "created"]
    assert data[0]["before"]["amount_cents"] == 100
    assert {e["entity"] for e in events(client)["items"]} >= {
        "account",
        "card",
        "statement",
        "card_charge",
        "statement_payment",
    }


def test_pagination_owner_isolation_and_purge(client, login):
    login()
    for name in ("A", "B", "C"):
        account(client, name)
    first = events(client, limit=2)
    last = events(client, limit=2, before_id=first["next_cursor"])
    assert (
        len(first["items"]) == 2
        and len(last["items"]) == 1
        and last["next_cursor"] is None
    )
    assert len({e["id"] for e in first["items"] + last["items"]}) == 3
    login("bob")
    assert events(client)["items"] == []
    assert (
        client.get(
            "/api/history", params={"before_id": first["next_cursor"]}
        ).status_code
        == 404
    )
    login()
    assert client.get("/api/history?limit=101").status_code == 422
    assert client.get("/api/history?entity=invalid").status_code == 422
    assert (
        client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        ).status_code
        == 200
    )
    login()
    assert events(client)["items"] == []


def test_history_rolls_back_with_financial_failure(client, login):
    login()
    gen = app.dependency_overrides[db_session]()
    db = next(gen)
    try:
        db.add(Account(owner="alice", name="Não persistir"))
        db.flush()
        assert db.scalar(select(func.count()).select_from(FinancialAudit)) == 1
        db.add(
            Transaction(
                owner="alice",
                **{**ENTRY, "amount_cents": -1, "date": date(2026, 11, 3)},
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        gen.close()
    assert events(client)["items"] == []
    assert client.get("/api/accounts").json() == []


def test_goal_metadata_defaults_and_audit_failure_rejects_financial_write(
    client, login, monkeypatch
):
    from tests.test_goals_lifecycle import create, update
    from app import audit

    login()
    row = create(client)
    row = update(client, row, archived=True, saved_cents=0).json()
    client.delete("/api/goals/" + row["id"] + "?expected_version=1")
    data = events(client, entity="goal")["items"]
    assert [e["action"] for e in data] == ["deleted", "updated", "created"]
    assert data[-1]["after"]["archived"] is False and data[-1]["after"]["version"] == 0
    assert data[1]["before"]["saved_cents"] == 1000

    def unavailable(row):
        raise RuntimeError("Histórico indisponível")

    monkeypatch.setattr(audit, "snapshot", unavailable)
    with pytest.raises(RuntimeError, match="Histórico indisponível"):
        client.post("/api/transactions", json=ENTRY)
    assert events(client, entity="transaction")["items"] == []
    assert client.get("/api/dashboard?month=2026-11").json()["transactions"] == []
