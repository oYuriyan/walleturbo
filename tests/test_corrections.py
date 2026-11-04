from uuid import uuid4
import pytest
from tests.test_cards import setup, buy, statement


def operation(client, body):
    r = client.get("/api/card-operations/" + body["request_id"])
    assert r.status_code == 200, r.text
    return r.json()


def correction(client, body, **changes):
    data = operation(client, body)
    return {
        **body,
        "request_id": str(uuid4()),
        "expected_revision": data["revision"],
        "reason": "Valor conferido no comprovante",
        **changes,
    }


def test_preview_and_atomic_redistribution_preserve_ids_and_history(client, login):
    _, card = setup(client, login)
    r, body = buy(client, card)
    before = r.json()
    change = correction(
        client, body, amount_cents=20003, installments=2, first_month="2026-12"
    )
    path = "/api/card-operations/" + body["request_id"]
    exported = client.get("/api/privacy/export").json()
    preview = client.post(path + "/preview", json=change)
    assert preview.status_code == 200, preview.text
    assert preview.json()["effects"] == [
        {"month": "2026-11", "before_cents": 3334, "after_cents": 0},
        {"month": "2026-12", "before_cents": 3334, "after_cents": 10002},
        {"month": "2027-01", "before_cents": 3333, "after_cents": 10001},
    ]
    assert client.get("/api/privacy/export").json() == exported
    r = client.put(path, json=change)
    assert r.status_code == 200, r.text
    assert [c["amount_cents"] for c in r.json()["charges"]] == [10002, 10001]
    assert [c["id"] for c in r.json()["charges"]] == [c["id"] for c in before[:2]]
    assert statement(client)["total_cents"] == 0
    assert (
        client.get("/api/dashboard?month=2026-12").json()["card_expense_cents"] == 10002
    )
    history = client.get("/api/history?entity=card_charge").json()["items"]
    assert sum(e["action"] == "updated" for e in history) == 2
    assert sum(e["action"] == "deleted" for e in history) == 1
    assert history[0]["after"]["correction_reason"] == change["reason"]
    # Reenviar a criação ou correção retorna o estado corrigido; não duplica parcelas.
    assert len(client.post("/api/card-purchases", json=body).json()) == 2
    assert client.put(path, json=change).json()["revision"] == r.json()["revision"]


def test_grow_installments_then_stale_revision_and_aba_review(client, login):
    _, card = setup(client, login)
    _, body = buy(client, card, installments=1)
    change = correction(client, body, installments=4)
    path = "/api/card-operations/" + body["request_id"]
    r = client.put(path, json=change)
    assert r.status_code == 200, r.text
    assert [c["amount_cents"] for c in r.json()["charges"]] == [2501, 2500, 2500, 2500]
    assert (
        client.put(path, json={**change, "request_id": str(uuid4())}).status_code == 409
    )
    change = correction(client, body)
    c = r.json()["charges"][0]
    for category in ("Outros", "Compras"):
        assert (
            client.put(
                "/api/card-charges/" + c["id"] + "/review",
                json={"category": category, "reviewed": True},
            ).status_code
            == 200
        )
    assert client.put(path, json=change).status_code == 409


@pytest.mark.parametrize("closed_month", ["2026-12", "2027-03"])
def test_old_or_target_closed_statement_blocks_everything(client, login, closed_month):
    _, card = setup(client, login)
    _, body = buy(client, card)
    if closed_month == "2027-03":
        s = client.post(
            f"/api/cards/{card['id']}/statements?month={closed_month}"
        ).json()
        amount = 0
    else:
        s = statement(client, closed_month)
        amount = 3334
    assert (
        client.post(
            f"/api/statements/{s['id']}/close", json={"expected_cents": amount}
        ).status_code
        == 200
    )
    change = correction(client, body, first_month="2027-03", installments=1)
    baseline = client.get("/api/privacy/export").json()
    path = "/api/card-operations/" + body["request_id"]
    assert client.post(path + "/preview", json=change).status_code == 409
    assert client.put(path, json=change).status_code == 409
    assert client.get("/api/privacy/export").json() == baseline


def test_delete_purchase_and_payment_keep_request_reservations_and_purge(client, login):
    a, card = setup(client, login)
    _, body = buy(client, card, installments=1)
    path = "/api/card-operations/" + body["request_id"]
    assert client.delete(path).status_code == 204
    assert client.post("/api/card-purchases", json=body).status_code == 409
    assert (
        client.post(
            "/api/card-purchases", json={**body, "amount_cents": 20000}
        ).status_code
        == 409
    )
    assert client.delete(path).status_code == 204
    new = {**body, "request_id": str(uuid4())}
    assert client.post("/api/card-purchases", json=new).status_code == 201
    s = statement(client)
    client.post(f"/api/statements/{s['id']}/close", json={"expected_cents": 10001})
    pay = {
        "request_id": str(uuid4()),
        "date": "2026-11-03",
        "account_id": a["id"],
        "amount_cents": 1000,
    }
    p = client.post(f"/api/statements/{s['id']}/payments", json=pay).json()
    assert client.delete("/api/statement-payments/" + p["id"]).status_code == 204
    assert (
        client.post(f"/api/statements/{s['id']}/payments", json=pay).status_code == 409
    )
    assert client.delete("/api/statement-payments/" + p["id"]).status_code == 204
    receipts = client.get("/api/privacy/export").json()["request_receipts"]
    assert sum(r["cancelled"] for r in receipts) == 2
    assert all("payload_hash" not in r and "owner" not in r for r in receipts)
    client.delete("/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"})
    login()
    assert client.get("/api/privacy/export").json()["request_receipts"] == []


def test_correction_ownership_imported_archived_and_refund_validation(client, login):
    _, card = setup(client, login)
    _, body = buy(client, card)
    change = correction(client, body)
    path = "/api/card-operations/" + body["request_id"]
    login("bob")
    assert client.get(path).status_code == 404
    assert client.post(path + "/preview", json=change).status_code == 404
    assert client.put(path, json=change).status_code == 404
    login()
    assert client.put(path, json={**change, "kind": "refund"}).status_code == 422
    assert client.put(path, json={**change, "reason": " "}).status_code == 422
    assert client.put(path, json={**change, "card_id": "other"}).status_code == 409
    s = statement(client)
    client.post(
        f"/api/statements/{s['id']}/import/confirm",
        json={
            "content": "data;descricao;valor;tipo\n2026-11-03;Mercado;12,34;despesa\n"
        },
    )
    imported = next(c for c in statement(client)["charges"] if c["imported"])
    fake = {**body, "request_id": imported["operation_id"]}
    assert (
        client.put(
            "/api/card-operations/" + imported["operation_id"],
            json=correction(client, fake, installments=1),
        ).status_code
        == 409
    )
    client.put(
        "/api/cards/" + card["id"],
        json={"name": card["name"], "archived": True, "expected_version": 0},
    )
    assert client.put(path, json=change).status_code == 409


def test_partial_correction_failure_rolls_back_parcels_receipt_and_audit(
    client, login, monkeypatch
):
    from app import audit

    _, card = setup(client, login)
    _, body = buy(client, card)
    change = correction(client, body, installments=2, amount_cents=20000)
    baseline = client.get("/api/privacy/export").json()
    original = audit.snapshot

    def fail(row):
        if getattr(row, "correction_reason", None):
            raise RuntimeError("Falha de histórico na correção")
        return original(row)

    monkeypatch.setattr(audit, "snapshot", fail)
    with pytest.raises(RuntimeError, match="Falha de histórico"):
        client.put("/api/card-operations/" + body["request_id"], json=change)
    assert client.get("/api/privacy/export").json() == baseline
