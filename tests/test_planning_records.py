from tests.test_finance import ENTRY, edit_body

PATH = "/api/planning/2026-11"


def test_stale_records_reject_confirmation_without_advancing_version(client, login):
    login()
    row = client.post("/api/transactions", json={**ENTRY, "date": "2026-11-01"}).json()
    before = client.get(PATH).json()
    assert (
        client.put(
            PATH + "/plan", json={"expected_version": 0, "records_complete": True}
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/transactions/" + row["id"],
            json=edit_body(row, description="Descrição corrigida"),
        ).status_code
        == 200
    )
    body = {
        "expected_version": 0,
        "records_complete": True,
        "expected_records_revision": before["records_revision"],
    }
    assert client.put(PATH + "/plan", json=body).status_code == 409
    current = client.get(PATH).json()
    assert current["version"] == 0 and current["figures"] == before["figures"]
    assert (
        client.put(
            PATH + "/plan",
            json={**body, "expected_records_revision": current["records_revision"]},
        ).status_code
        == 200
    )
    assert client.get(PATH).json()["plan"]["records_complete"]
    changed = client.get("/api/transactions/" + row["id"]).json()
    client.put(
        "/api/transactions/" + row["id"],
        json=edit_body(changed, description=row["description"]),
    )
    after = client.get(PATH).json()
    assert after["figures"] == before["figures"]
    assert not after["plan"]["records_complete"]
    assert after["records_revision"] != before["records_revision"]


def test_records_revision_scoped_and_unconfirmed_settings_allowed(client, login):
    login()
    a = client.get(PATH).json()["records_revision"]
    assert a != client.get("/api/planning/2026-12").json()["records_revision"]
    login("bob")
    assert a != client.get(PATH).json()["records_revision"]
    assert (
        client.put(
            PATH + "/plan",
            json={
                "expected_version": 0,
                "records_complete": True,
                "expected_records_revision": a,
            },
        ).status_code
        == 409
    )
    assert (
        client.put(
            PATH + "/plan", json={"expected_version": 0, "buffer_cents": 100}
        ).status_code
        == 200
    )
