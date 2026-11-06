import pytest
from app import audit
from app.db import Budget

PATH = "/api/planning/2026-11"


def test_shared_version_blocks_stale_write_delete_and_recreation(client, login):
    login()
    assert client.get(PATH).json()["version"] == 0
    body = {"category": "Compras", "amount_cents": 1000, "expected_version": 0}
    assert client.put(PATH + "/budget", json=body).json()["version"] == 1
    assert (
        client.put(
            PATH + "/plan", json={"expected_version": 0, "buffer_cents": 100}
        ).status_code
        == 409
    )
    assert client.delete(PATH + "/budget/Compras?expected_version=0").status_code == 409
    assert client.delete(PATH + "/budget/Compras?expected_version=1").status_code == 204
    assert client.put(PATH + "/budget", json=body).status_code == 409
    assert (
        client.put(PATH + "/budget", json={**body, "expected_version": 2}).status_code
        == 200
    )
    assert client.get(PATH).json()["version"] == 3
    events = client.get("/api/history?entity=budget").json()["items"]
    assert {e["action"] for e in events} == {"created", "deleted"}
    assert all(e["entity_id"] == "2026-11:Compras" for e in events)


def test_planning_revision_is_scoped_and_required(client, login):
    login()
    assert client.put(PATH + "/plan", json={}).status_code == 422
    assert client.delete(PATH + "/budget/Compras").status_code == 422
    assert (
        client.put(
            PATH + "/plan", json={"expected_version": 0, "buffer_cents": 100}
        ).status_code
        == 200
    )
    assert client.get("/api/planning/2026-12").json()["version"] == 0
    login("bob")
    assert client.get(PATH).json()["version"] == 0
    assert client.get("/api/history?entity=month_plan").json()["items"] == []


def test_audit_failure_rolls_back_planning_version_and_budget(
    client, login, monkeypatch
):
    login()
    original = audit.snapshot

    def fail(row):
        if isinstance(row, Budget):
            raise RuntimeError("Falha de histórico simulada")
        return original(row)

    monkeypatch.setattr(audit, "snapshot", fail)
    with pytest.raises(RuntimeError, match="Falha de histórico"):
        client.put(
            PATH + "/budget",
            json={"expected_version": 0, "category": "Compras", "amount_cents": 1000},
        )
    assert client.get(PATH).json()["version"] == 0
    assert client.get(PATH).json()["budgets"] == []
    assert client.get("/api/history").json()["items"] == []


def test_planning_history_and_versions_are_erased(client, login):
    login()
    client.put(PATH + "/plan", json={"expected_version": 0, "buffer_cents": 100})
    exported = client.get("/api/privacy/export").json()
    assert exported["month_plans"][0]["version"] == 1
    assert any(e["entity"] == "month_plan" for e in exported["financial_history"])
    assert (
        client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        ).status_code
        == 200
    )
    login()
    assert client.get(PATH).json()["version"] == 0
    assert client.get("/api/history").json()["items"] == []
