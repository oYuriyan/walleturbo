from sqlalchemy import event
import pytest
from app.db import FinancialAudit
from tests.test_finance import ENTRY, CSV, edit_body
from tests.test_import_links import payload
from tests.test_cards import setup, buy, statement


def prepare(client, login, card=False):
    if card:
        _, c = setup(client, login)
        purchase, _ = buy(
            client, c, date="2026-11-03", amount_cents=1234, installments=1
        )
        row = purchase.json()[0]
        path = f"/api/statements/{statement(client)['id']}/import"
    else:
        login()
        row = client.post(
            "/api/transactions", json={**ENTRY, "description": "Manual"}
        ).json()
        path = "/api/import"
    assert client.post(path + "/confirm", json=payload(row)).status_code == 200
    preview = client.post(path + "/preview", json={"content": CSV}).json()
    origin = preview["known_origins"][0]
    assert origin["releasable"]
    body = {
        "content": CSV,
        "release": {
            "source_index": 0,
            "resource_id": row["id"],
            "expected_version": origin["target"]["version"],
            "expected_origin_version": origin["version"],
            "reason": "Destino incorreto",
        },
    }
    return path, row, body


@pytest.mark.parametrize("card", [False, True])
def test_release_preserves_finances_and_stale_requests_cannot_restore_link(
    client, login, card
):
    path, row, body = prepare(client, login, card)
    before = client.get("/api/privacy/export").json()
    assert client.post(path + "/unlink", json=body).json() == {"released": 1}
    after = client.get("/api/privacy/export").json()
    for entity in before.keys() - {"import_marks", "financial_history"}:
        assert after[entity] == before[entity]
    assert after["import_marks"][0]["version"] == 2
    history = client.get("/api/history?entity=import_link").json()["items"]
    assert len(history) == 2
    assert any(
        h["action"] == "deleted" and h["after"]["reason"] == "Destino incorreto"
        for h in history
    )
    assert client.post(path + "/unlink", json=body).status_code == 409
    assert client.post(path + "/confirm", json=payload(row)).status_code == 409
    assert client.post(path + "/confirm", json={"content": CSV}).status_code == 409
    preview = client.post(path + "/preview", json={"content": CSV}).json()
    assert preview["known_origins"] == [] and preview["origin_versions"] == [2]
    relink = payload(row)
    relink["links"][0]["expected_origin_version"] = 2
    assert client.post(path + "/confirm", json=relink).json()["linked"] == 1
    assert client.post(path + "/unlink", json=body).status_code == 409


def test_released_origin_can_be_imported_as_independent_occurrence_after_new_preview(
    client, login
):
    path, _, body = prepare(client, login)
    assert client.post(path + "/unlink", json=body).status_code == 200
    preview = client.post(path + "/preview", json={"content": CSV}).json()
    confirmed = {"content": CSV, "origin_versions": preview["origin_versions"]}
    assert client.post(path + "/confirm", json=confirmed).json()["created"] == 1
    assert client.post(path + "/confirm", json=confirmed).json()["created"] == 0
    assert len(client.get("/api/privacy/export").json()["transactions"]) == 2
    assert not client.post(path + "/preview", json={"content": CSV}).json()[
        "known_origins"
    ][0]["releasable"]


def test_remap_after_release_rejects_old_assignment_and_release(client, login):
    path, old, body = prepare(client, login)
    new = client.post("/api/transactions", json=ENTRY).json()
    assert client.post(path + "/unlink", json=body).status_code == 200
    relink = payload(new)
    relink["links"][0]["expected_origin_version"] = 2
    assert client.post(path + "/confirm", json=relink).json()["linked"] == 1
    assert client.post(path + "/confirm", json=relink).json()["linked"] == 1
    assert client.post(path + "/confirm", json=payload(old)).status_code == 409
    assert client.post(path + "/unlink", json=body).status_code == 409
    exported = client.get("/api/privacy/export").json()
    assert exported["import_marks"][0]["resource_id"] == new["id"]
    assert len(exported["transactions"]) == 2


@pytest.mark.parametrize(
    "problem",
    ["owner", "index", "version", "origin_version", "reason", "deleted", "edited"],
)
def test_release_rejects_unreviewed_or_unavailable_state_without_writes(
    client, login, problem
):
    path, row, body = prepare(client, login)
    if problem == "owner":
        login("bob")
    elif problem == "index":
        body["release"]["source_index"] = 1
    elif problem == "version":
        body["release"]["expected_version"] = 99
    elif problem == "origin_version":
        body["release"]["expected_origin_version"] = 99
    elif problem == "reason":
        body["release"]["reason"] = "  "
    elif problem == "deleted":
        client.delete(f"/api/transactions/{row['id']}?expected_version=1")
    else:
        client.put(
            f"/api/transactions/{row['id']}", json=edit_body(row, amount_cents=2000)
        )
    before = client.get("/api/privacy/export").json()
    assert client.post(path + "/unlink", json=body).status_code in (409, 422)
    assert client.get("/api/privacy/export").json() == before


def test_original_import_identity_cannot_be_released(client, login):
    login()
    client.post("/api/import/confirm", json={"content": CSV})
    preview = client.post("/api/import/preview", json={"content": CSV}).json()
    origin = preview["known_origins"][0]
    assert not origin["releasable"]
    body = {
        "content": CSV,
        "release": {
            "source_index": 0,
            "resource_id": origin["resource_id"],
            "expected_version": origin["target"]["version"],
            "expected_origin_version": origin["version"],
            "reason": "Apagar origem",
        },
    }
    assert client.post("/api/import/unlink", json=body).status_code == 409


def test_release_and_history_roll_back_together(client, login):
    path, _, body = prepare(client, login)
    before = client.get("/api/privacy/export").json()

    def fail(mapper, connection, target):
        if target.entity == "import_link" and target.action == "deleted":
            raise RuntimeError("histórico indisponível")

    event.listen(FinancialAudit, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="histórico indisponível"):
            client.post(path + "/unlink", json=body)
    finally:
        event.remove(FinancialAudit, "before_insert", fail)
    assert client.get("/api/privacy/export").json() == before


def test_closed_statement_does_not_release_link(client, login):
    path, _, body = prepare(client, login, card=True)
    statement_path = path.removesuffix("/import")
    bill = client.get(statement_path).json()
    response = client.post(
        statement_path + "/close",
        json={
            "expected_cents": 1234,
            "expected_revision": bill["revision"],
        },
    )
    assert response.status_code == 200, response.text
    before = client.get("/api/privacy/export").json()
    assert client.post(path + "/unlink", json=body).status_code == 409
    assert client.get("/api/privacy/export").json() == before


def test_current_preview_allows_release_after_target_correction(client, login):
    path, row, body = prepare(client, login)
    changed = client.put(
        f"/api/transactions/{row['id']}", json=edit_body(row, amount_cents=2000)
    ).json()
    preview = client.post(path + "/preview", json={"content": CSV}).json()
    assert preview["possible_duplicates"] == []
    assert preview["known_origins"][0]["releasable"]
    body["release"]["expected_version"] = changed["version"]
    assert client.post(path + "/unlink", json=body).status_code == 200
    assert client.get(f"/api/transactions/{row['id']}").json()["amount_cents"] == 2000
