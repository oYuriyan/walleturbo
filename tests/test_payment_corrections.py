from uuid import uuid4
import pytest
from tests.test_cards import setup, buy, statement
from tests.test_balances import opening, balances


def fixture(client, login, reference=True):
    a, card = setup(client, login)
    b = client.post("/api/accounts", json={"name": "Reserva"}).json()
    if reference:
        opening(client, a["id"], amount_cents=10000)
        opening(client, b["id"], amount_cents=20000)
    buy(client, card, amount_cents=15000, installments=1)
    s = statement(client)
    assert (
        client.post(
            f"/api/statements/{s['id']}/close",
            json={
                "expected_cents": 15000,
                "expected_revision": client.get(f"/api/statements/{s['id']}")
                .json()
                .get("revision", "0" * 64),
            },
        ).status_code
        == 200
    )
    original = {
        "request_id": str(uuid4()),
        "account_id": a["id"],
        "date": "2026-11-03",
        "amount_cents": 6000,
    }
    p = client.post(f"/api/statements/{s['id']}/payments", json=original).json()
    assert (
        client.post(
            f"/api/statements/{s['id']}/payments",
            json={**original, "request_id": str(uuid4()), "amount_cents": 3000},
        ).status_code
        == 201
    )
    return a, b, card, s, p, original


def body(p, **changes):
    return {
        "request_id": str(uuid4()),
        "account_id": p["account_id"],
        "date": p["date"],
        "amount_cents": p["amount_cents"],
        "expected_version": p["version"],
        "as_of": "2026-12-31",
        "reason": "Conferido no comprovante",
        **changes,
    }


def test_payment_correction_cash_accounts_statement_and_replay(client, login):
    a, b, _, s, p, original = fixture(client, login)
    path = "/api/statement-payments/" + p["id"]
    change = body(p, account_id=b["id"], date="2026-12-02", amount_cents=4000)
    before = client.get("/api/privacy/export").json()
    preview = client.post(path + "/preview", json=change)
    assert preview.status_code == 200, preview.text
    effects = {r["account_id"]: r for r in preview.json()["accounts"]}
    assert (effects[a["id"]]["before_cents"], effects[a["id"]]["after_cents"]) == (
        1000,
        7000,
    )
    assert (effects[b["id"]]["before_cents"], effects[b["id"]]["after_cents"]) == (
        20000,
        16000,
    )
    assert preview.json()["statement"]["remaining_after_cents"] == 8000
    assert preview.json()["cash_changes"] == [
        {"month": "2026-11", "delta_cents": 6000},
        {"month": "2026-12", "delta_cents": -4000},
    ]
    assert client.get("/api/privacy/export").json() == before
    result = client.put(path, json=change)
    assert result.status_code == 200, result.text
    updated = result.json()["payment"]
    assert (
        updated["id"] == p["id"]
        and updated["request_id"] == p["request_id"]
        and updated["version"] == 2
    )
    assert updated["correction_reason"] == change["reason"]
    report = {
        r["id"]: r["balance_cents"] for r in balances(client, "2026-12-31")["accounts"]
    }
    assert report[a["id"]] == 7000 and report[b["id"]] == 16000
    november = client.get("/api/dashboard?month=2026-11").json()
    assert november["expense_cents"] == 15000 and november["card_payment_cents"] == 3000
    assert (
        client.get("/api/dashboard?month=2026-12").json()["card_payment_cents"] == 4000
    )
    baseline = client.get("/api/privacy/export").json()
    assert client.put(path, json=change).json()["payment"] == updated
    assert (
        client.post(f"/api/statements/{s['id']}/payments", json=original).json()
        == updated
    )
    assert client.get("/api/privacy/export").json() == baseline
    history = client.get("/api/history?entity=statement_payment").json()["items"]
    assert (
        history[0]["before"]["account_id"] == a["id"]
        and history[0]["after"]["account_id"] == b["id"]
    )


def test_previews_unknown_balance_before_reference_and_future_payment(client, login):
    a, b, _, _, p, _ = fixture(client, login, reference=False)
    path = "/api/statement-payments/" + p["id"] + "/preview"
    data = client.post(
        path, json=body(p, account_id=b["id"], as_of="2026-11-02", date="2026-12-02")
    ).json()
    assert all(
        r["before_cents"] is None
        and r["after_cents"] is None
        and r["delta_cents"] is None
        for r in data["accounts"]
    )
    opening(client, a["id"], date="2026-11-01", amount_cents=10000)
    data = client.post(path, json=body(p, date="2026-10-31", amount_cents=4000)).json()[
        "accounts"
    ][0]
    assert data["before_cents"] == 1000 and data["after_cents"] == 7000
    data = client.post(path, json=body(p, as_of="2026-10-31")).json()["accounts"][0]
    assert data["status"] == "before_reference" and data["after_cents"] is None
    data = client.post(
        path, json=body(p, as_of="2026-11-02", date="2026-12-02")
    ).json()["accounts"][0]
    assert data["before_cents"] == 10000 and data["after_cents"] == 10000


def test_revalidate_other_payments_after_preview_and_rollback_receipt(client, login):
    _, _, _, s, p, original = fixture(client, login)
    path = "/api/statement-payments/" + p["id"]
    change = body(p, amount_cents=10000)
    assert client.post(path + "/preview", json=change).status_code == 200
    assert (
        client.post(
            f"/api/statements/{s['id']}/payments",
            json={**original, "request_id": str(uuid4()), "amount_cents": 3000},
        ).status_code
        == 201
    )
    before = client.get("/api/privacy/export").json()
    assert client.put(path, json=change).status_code == 409
    assert client.get("/api/privacy/export").json() == before
    assert client.put(path, json={**change, "amount_cents": 9000}).status_code == 200


def test_payment_versions_aba_stale_delete_and_cancelled_replays(client, login):
    _, _, _, s, p, original = fixture(client, login)
    path = "/api/statement-payments/" + p["id"]
    for amount in (5000, 6000):
        current = client.get(path).json()["payment"]
        assert (
            client.put(path, json=body(current, amount_cents=amount)).status_code == 200
        )
    assert client.get(path).json()["payment"]["version"] == 3
    assert client.put(path, json=body(p)).status_code == 409
    assert client.delete(path).status_code == 422
    assert client.delete(path + "?expected_version=1").status_code == 409
    assert client.delete(path + "?expected_version=3").status_code == 204
    assert client.delete(path + "?expected_version=3").status_code == 204
    assert client.put(path, json=body(p)).status_code == 404
    assert (
        client.post(f"/api/statements/{s['id']}/payments", json=original).status_code
        == 409
    )


def test_archived_accounts_and_card_correct_existing_links_only(client, login):
    a, b, card, _, p, _ = fixture(client, login)
    path = "/api/statement-payments/" + p["id"]
    for kind, row in (("cards", card), ("accounts", a), ("accounts", b)):
        assert (
            client.put(
                f"/api/{kind}/{row['id']}",
                json={"name": row["name"], "archived": True, "expected_version": 0},
            ).status_code
            == 200
        )
    assert client.put(path, json=body(p, amount_cents=5000)).status_code == 200
    p = client.get(path).json()["payment"]
    assert client.put(path, json=body(p, account_id=b["id"])).status_code == 409
    active = client.post("/api/accounts", json={"name": "Ativa"}).json()
    assert client.put(path, json=body(p, account_id=active["id"])).status_code == 200


def test_payment_correction_owner_validation_and_privacy(client, login):
    _, _, _, s, p, _ = fixture(client, login)
    path = "/api/statement-payments/" + p["id"]
    login("bob")
    assert client.get(path).status_code == 404
    assert client.post(path + "/preview", json=body(p)).status_code == 404
    assert client.put(path, json=body(p)).status_code == 404
    login()
    for changes in (
        {"expected_version": True},
        {"expected_version": 0},
        {"reason": " "},
        {"date": "1899-12-31"},
        {"as_of": "9999-01-01"},
        {"statement_id": s["id"]},
        {"amount_cents": 0},
    ):
        assert client.put(path, json=body(p, **changes)).status_code == 422
    assert client.put(path, json=body(p, account_id="inexistente")).status_code == 404
    assert client.put(path, json=body(p, amount_cents=5000)).status_code == 200
    assert "payment_edit" in {
        r["scope"] for r in client.get("/api/privacy/export").json()["request_receipts"]
    }
    client.delete("/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"})
    login()
    exported = client.get("/api/privacy/export").json()
    assert (
        exported["request_receipts"] == []
        and exported["statement_payments"] == []
        and exported["financial_history"] == []
    )


def test_payment_correction_audit_failure_rolls_back_everything(
    client, login, monkeypatch
):
    from app import audit

    _, b, _, _, p, _ = fixture(client, login)
    before = client.get("/api/privacy/export").json()
    old = audit.snapshot

    def fail(row):
        if getattr(row, "correction_reason", None):
            raise RuntimeError("Falha no histórico do pagamento")
        return old(row)

    monkeypatch.setattr(audit, "snapshot", fail)
    with pytest.raises(RuntimeError, match="Falha no histórico"):
        client.put(
            "/api/statement-payments/" + p["id"], json=body(p, account_id=b["id"])
        )
    assert client.get("/api/privacy/export").json() == before
