from uuid import uuid4
import pytest
from sqlalchemy import event
from app.db import FinancialAudit
from tests.test_cards import buy, delete_operation
from tests.test_corrections import correction
from tests.test_ofx_card import prepare, path, body, SGML, XML


def imported(client, login, index=0):
    card, source, destination = prepare(client, login)
    result = client.post(
        path(source) + "/confirm",
        json=body(excluded_indices=[i for i in range(3) if i != index]),
    )
    assert result.status_code == 200, result.text
    return card, source, destination


def change(client, source, destination, index=0):
    review = client.post(path(source) + "/preview", json=body()).json()
    origin = next(o for o in review["known_origins"] if o["source_index"] == index)
    return {
        "content": SGML,
        "source_index": index,
        "resource_id": origin["resource_id"],
        "destination_statement_id": destination["id"],
        "expected_version": origin["target"]["version"],
        "expected_origin_version": origin["version"],
        "reason": "Competência conferida na fatura",
    }


def confirmed(client, source, payload):
    review = client.post(path(source) + "/relocate/preview", json=payload)
    assert review.status_code == 200, review.text
    return {
        **payload,
        "expected_revision": review.json()["revision"],
        "request_id": str(uuid4()),
        "reviewed": True,
    }


def test_preview_move_and_replay_preserve_record_corrections_identity_and_history(
    client, login
):
    card, source, destination = imported(client, login)
    row = client.get("/api/privacy/export").json()["card_charges"][0]
    corrected = correction(
        client,
        {
            "request_id": row["operation_id"],
            "card_id": card["id"],
            "first_month": source["month"],
            "date": "2026-11-05",
            "description": "Descrição e valor corrigidos",
            "amount_cents": 13000,
            "installments": 1,
            "kind": "expense",
            "category": "Outros",
            "reviewed": False,
        },
    )
    response = client.put("/api/card-operations/" + row["operation_id"], json=corrected)
    assert response.status_code == 200, response.text
    row = response.json()["charges"][0]
    result = client.put(
        f"/api/card-charges/{row['id']}/review",
        json={
            "expected_version": row["version"],
            "category": "Compras",
            "reviewed": True,
        },
    )
    assert result.status_code == 200
    payload = change(client, source, destination)
    before = client.get("/api/privacy/export").json()
    move = confirmed(client, source, payload)
    assert client.get("/api/privacy/export").json() == before
    response = client.post(path(source) + "/relocate", json=move)
    assert response.status_code == 200, response.text
    assert client.post(path(source) + "/relocate", json=move).json() == response.json()
    exported = client.get("/api/privacy/export").json()
    moved = exported["card_charges"][0]
    original = before["card_charges"][0]
    for key, value in original.items():
        if key not in {"statement_id", "version", "correction_reason"}:
            assert moved[key] == value
    assert (
        moved["statement_id"] == destination["id"]
        and moved["version"] == original["version"] + 1
    )
    assert client.get(f"/api/statements/{source['id']}").json()["total_cents"] == 0
    assert (
        client.get(f"/api/statements/{destination['id']}").json()["total_cents"]
        == 13000
    )
    assert not exported["transactions"] and not exported["statement_payments"]
    assert (
        client.post(
            path(source) + "/confirm", json=body(excluded_indices=[1, 2])
        ).status_code
        == 409
    )
    assert client.post(
        path(destination) + "/confirm", json=body(XML, excluded_indices=[0, 1])
    ).json() == {"created": 0, "duplicates": 1, "skipped": 2}
    history = client.get("/api/history?entity=import_relocation").json()["items"]
    assert len(history) == 1 and history[0]["before"]["month"] == source["month"]
    assert history[0]["after"]["month"] == destination["month"]
    assert history[0]["after"]["reason"] == payload["reason"]
    assert (
        len(exported["import_marks"]) == 1
        and exported["import_marks"][0]["version"] == 2
    )


def test_return_to_previous_month_increases_versions_and_rejects_stale_preview(
    client, login
):
    _, source, destination = imported(client, login)
    old = confirmed(client, source, change(client, source, destination))
    assert client.post(path(source) + "/relocate", json=old).status_code == 200
    back = confirmed(client, destination, change(client, destination, source))
    assert client.post(path(destination) + "/relocate", json=back).status_code == 200
    assert (
        client.post(
            path(source) + "/relocate", json={**old, "request_id": str(uuid4())}
        ).status_code
        == 409
    )
    before = client.get("/api/privacy/export").json()
    assert client.post(path(source) + "/relocate", json=old).status_code == 200
    assert client.get("/api/privacy/export").json() == before
    assert before["import_marks"][0]["version"] == 3


@pytest.mark.parametrize("side", ["source", "destination"])
def test_changed_statement_rejects_confirm_without_partial_writes(client, login, side):
    card, source, destination = imported(client, login)
    move = confirmed(client, source, change(client, source, destination))
    target = source if side == "source" else destination
    assert (
        buy(client, card, first_month=target["month"], installments=1)[0].status_code
        == 201
    )
    before = client.get("/api/privacy/export").json()
    response = client.post(path(source) + "/relocate", json=move)
    assert response.status_code == 409
    assert client.get("/api/privacy/export").json() == before


@pytest.mark.parametrize("side", ["source", "destination"])
def test_closed_statement_blocks_relocation(client, login, side):
    _, source, destination = imported(client, login)
    payload = change(client, source, destination)
    target = source if side == "source" else destination
    if side == "source":
        row = client.get("/api/privacy/export").json()["card_charges"][0]
        client.put(
            f"/api/card-charges/{row['id']}/review",
            json={
                "expected_version": row["version"],
                "category": "Outros",
                "reviewed": True,
            },
        )
        payload = change(client, source, destination)
    snapshot = client.get(f"/api/statements/{target['id']}").json()
    response = client.post(
        f"/api/statements/{target['id']}/close",
        json={
            "expected_cents": snapshot["total_cents"],
            "expected_revision": snapshot["revision"],
        },
    )
    assert response.status_code == 200, response.text
    assert (
        client.post(path(source) + "/relocate/preview", json=payload).status_code == 409
    )


def test_other_card_owner_archive_and_unreviewed_confirmation_are_blocked(
    client, login
):
    card, source, destination = imported(client, login)
    payload = change(client, source, destination)
    other = client.post("/api/cards", json={"name": "Outro", "due_day": 10}).json()
    bill = client.post(f"/api/cards/{other['id']}/statements?month=2026-12").json()
    assert (
        client.post(
            path(source) + "/relocate/preview",
            json={**payload, "destination_statement_id": bill["id"]},
        ).status_code
        == 409
    )
    move = confirmed(client, source, payload)
    assert (
        client.post(
            path(source) + "/relocate", json={**move, "reviewed": False}
        ).status_code
        == 422
    )
    login("bob")
    assert client.post(path(source) + "/relocate", json=move).status_code == 404
    login()
    response = client.put(
        f"/api/cards/{card['id']}",
        json={
            "name": card["name"],
            "archived": True,
            "expected_version": card["version"],
        },
    )
    assert response.status_code == 200, response.text
    assert (
        client.post(path(source) + "/relocate/preview", json=payload).status_code == 409
    )


def test_deleted_source_cannot_be_relocated_or_recreated(client, login):
    _, source, destination = imported(client, login)
    payload = change(client, source, destination)
    row = client.get("/api/privacy/export").json()["card_charges"][0]
    assert (
        delete_operation(
            client, "/api/card-operations/" + row["operation_id"]
        ).status_code
        == 204
    )
    before = client.get("/api/privacy/export").json()
    assert (
        client.post(path(source) + "/relocate/preview", json=payload).status_code == 409
    )
    assert client.get("/api/privacy/export").json() == before


def test_additional_links_block_move_until_explicit_unlink(client, login):
    _, source, destination = imported(client, login)
    payload = change(client, source, destination)
    alias = SGML.replace("CARD-001", "ALIAS-001")
    link = {
        "source_index": 0,
        "resource_id": payload["resource_id"],
        "expected_version": payload["expected_version"],
        "expected_origin_version": 0,
    }
    response = client.post(
        path(source) + "/confirm",
        json=body(alias, excluded_indices=[1, 2], links=[link]),
    )
    assert response.status_code == 200, response.text
    assert (
        client.post(path(source) + "/relocate/preview", json=payload).status_code == 409
    )
    release = {
        **link,
        "expected_origin_version": 1,
        "reason": "Vínculo adicional incorreto",
    }
    assert (
        client.post(
            path(source) + "/unlink", json={"content": alias, "release": release}
        ).status_code
        == 200
    )
    assert (
        client.post(
            path(source) + "/relocate", json=confirmed(client, source, payload)
        ).status_code
        == 200
    )


@pytest.mark.parametrize("index", [0, 1])
def test_payment_requires_explicit_reversal_and_reopening_before_move(
    client, login, index
):
    card, source, destination = imported(client, login, index)
    paid_bill = source if index == 0 else destination
    if index == 1:
        assert (
            buy(
                client,
                card,
                first_month=destination["month"],
                installments=1,
                amount_cents=3000,
            )[0].status_code
            == 201
        )
    if index == 0:
        row = client.get("/api/privacy/export").json()["card_charges"][0]
        client.put(
            f"/api/card-charges/{row['id']}/review",
            json={
                "expected_version": row["version"],
                "category": "Outros",
                "reviewed": True,
            },
        )
    payload = change(client, source, destination, index)
    snapshot = client.get(f"/api/statements/{paid_bill['id']}").json()
    assert (
        client.post(
            f"/api/statements/{paid_bill['id']}/close",
            json={
                "expected_cents": snapshot["total_cents"],
                "expected_revision": snapshot["revision"],
            },
        ).status_code
        == 200
    )
    account = client.get("/api/accounts").json()[0]
    payment = client.post(
        f"/api/statements/{paid_bill['id']}/payments",
        json={
            "request_id": str(uuid4()),
            "account_id": account["id"],
            "amount_cents": 2500,
            "date": "2026-11-10",
        },
    )
    assert payment.status_code == 201, payment.text
    before = client.get("/api/privacy/export").json()
    response = client.post(path(source) + "/relocate/preview", json=payload)
    assert response.status_code == 409, response.text
    assert client.get("/api/privacy/export").json() == before
    snapshot = client.get(f"/api/statements/{paid_bill['id']}").json()
    assert (
        client.post(
            f"/api/statements/{paid_bill['id']}/reopen?expected_revision={snapshot['revision']}"
        ).status_code
        == 409
    )
    payment = payment.json()
    assert (
        client.delete(
            f"/api/statement-payments/{payment['id']}?expected_version={payment['version']}"
        ).status_code
        == 204
    )
    snapshot = client.get(f"/api/statements/{paid_bill['id']}").json()
    assert (
        client.post(
            f"/api/statements/{paid_bill['id']}/reopen?expected_revision={snapshot['revision']}"
        ).status_code
        == 200
    )
    move = confirmed(client, source, change(client, source, destination, index))
    assert client.post(path(source) + "/relocate", json=move).status_code == 200


def test_audit_failure_rolls_back_charge_source_and_request_receipts(client, login):
    _, source, destination = imported(client, login)
    move = confirmed(client, source, change(client, source, destination))
    before = client.get("/api/privacy/export").json()

    def fail(mapper, connection, row):
        if row.entity == "import_relocation":
            raise RuntimeError("audit failed")

    event.listen(FinancialAudit, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="audit failed"):
            client.post(path(source) + "/relocate", json=move)
    finally:
        event.remove(FinancialAudit, "before_insert", fail)
    assert client.get("/api/privacy/export").json() == before
    assert client.post(path(source) + "/relocate", json=move).status_code == 200


def test_altered_ofx_or_reason_cannot_reuse_move_preview(client, login):
    _, source, destination = imported(client, login)
    move = confirmed(client, source, change(client, source, destination))
    before = client.get("/api/privacy/export").json()
    for changes in (
        {"content": SGML.replace("<TRNAMT>-123.45", "<TRNAMT>-120.00", 1)},
        {"reason": "Outro motivo sem nova simulação"},
    ):
        response = client.post(path(source) + "/relocate", json={**move, **changes})
        assert response.status_code == 409, response.text
        assert client.get("/api/privacy/export").json() == before
