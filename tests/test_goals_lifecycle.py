import pytest
from tests.test_planning import add

GOAL = {
    "name": "Reserva",
    "target_cents": 50000,
    "saved_cents": 1000,
    "deadline": "2027-12-01",
}


def create(client, **values):
    r = client.post("/api/goals", json={**GOAL, **values})
    assert r.status_code == 201, r.text
    return r.json()


def update(client, row, **values):
    return client.put(
        "/api/goals/" + row["id"],
        json={
            **{k: row[k] for k in GOAL},
            "archived": row["archived"],
            "expected_version": row["version"],
            **values,
        },
    )


def test_goal_version_preserves_changes_and_validates_corrections(client, login):
    login()
    row = create(client)
    assert row["version"] == 0 and row["archived"] is False and "owner" not in row
    assert update(client, row).json()["version"] == 0
    changed = update(client, row, name="Emergência", saved_cents=2000).json()
    assert changed["version"] == 1 and changed["saved_cents"] == 2000
    assert update(client, row, saved_cents=100).status_code == 409
    assert update(client, changed, target_cents=1000).status_code == 422
    assert update(client, changed, archived="false").status_code == 422
    assert update(client, changed, expected_version=True).status_code == 422
    assert update(client, changed, name="  ").status_code == 422
    assert client.put("/api/goals/" + row["id"], json=GOAL).status_code == 422
    assert client.post("/api/goals", json={**GOAL, "archived": True}).status_code == 422


def test_archived_goal_does_not_consume_simulated_capacity_but_keeps_values(
    client, login
):
    login()
    archived = create(
        client,
        name="Pausada",
        deadline="2027-01-01",
        target_cents=2000,
        saved_cents=500,
    )
    active = create(client, name="Ativa", target_cents=100000)
    add(client, 10000, "income", "Renda")
    client.put(
        "/api/planning/2026-11/plan",
        json={
            **({"records_complete": True}),
            "expected_records_revision": client.get("/api/planning/2026-11").json()[
                "records_revision"
            ],
            "expected_version": client.get(
                ("/api/planning/2026-11/plan").rsplit("/", 1)[0]
            ).json()["version"],
        },
    )
    before = client.get("/api/planning/2026-11").json()
    assert [g["id"] for g in before["goals"]] == [archived["id"], active["id"]]
    row = update(client, archived, archived=True).json()
    after = client.get("/api/planning/2026-11").json()
    assert [g["id"] for g in after["goals"]] == [active["id"]]
    assert before["capacity_cents"] == after["capacity_cents"] == 10000
    assert before["figures"] == after["figures"]
    dashboard = client.get("/api/dashboard?month=2026-11").json()["goals"]
    assert next(g for g in dashboard if g["id"] == row["id"])["saved_cents"] == 500
    assert len(client.get("/api/privacy/export").json()["goals"]) == 2
    assert update(client, row, archived=False).status_code == 200
    assert len(client.get("/api/planning/2026-11").json()["goals"]) == 2


def test_delete_requires_archival_current_version_and_zero_reserve(client, login):
    login()
    row = create(client)
    path = "/api/goals/" + row["id"]
    assert client.delete(path + "?expected_version=0").status_code == 409
    row = update(client, row, archived=True).json()
    assert client.delete(path + "?expected_version=0").status_code == 409
    assert client.delete(path + "?expected_version=1").status_code == 409
    # Zerar é correção declarada; não há saque ou alteração do caixa.
    row = update(client, row, saved_cents=0).json()
    assert client.delete(path + "?expected_version=2").status_code == 204
    assert client.get("/api/privacy/export").json()["goals"] == []
    assert update(client, row).status_code == 404


def test_goal_owner_isolation_and_privacy(client, login):
    login()
    row = create(client)
    login("bob")
    assert update(client, row, archived=True).status_code == 404
    assert (
        client.delete("/api/goals/" + row["id"] + "?expected_version=0").status_code
        == 404
    )
    assert client.get("/api/privacy/export").json()["goals"] == []
    login()
    update(client, row, archived=True)
    exported = client.get("/api/privacy/export").json()["goals"][0]
    assert exported["archived"] and exported["version"] == 1
    assert (
        client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        ).status_code
        == 200
    )
    login()
    assert client.get("/api/privacy/export").json()["goals"] == []
