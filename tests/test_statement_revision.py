from tests.test_cards import setup, buy, statement


def test_reconciliation_rejects_changed_category_even_with_same_total(client, login):
    _, card = setup(client, login)
    buy(client, card, installments=1)
    old = statement(client)
    charge = old["charges"][0]
    response = client.put(
        "/api/card-charges/" + charge["id"] + "/review",
        json={
            "expected_version": charge["version"],
            "category": "Outros",
            "reviewed": True,
        },
    )
    assert response.status_code == 200
    path = "/api/statements/" + old["id"] + "/close"
    assert (
        client.post(
            path,
            json={
                "expected_cents": old["total_cents"],
                "expected_revision": old["revision"],
            },
        ).status_code
        == 409
    )
    current = statement(client)
    assert current["status"] == "open" and current["total_cents"] == old["total_cents"]
    assert (
        client.post(
            path,
            json={
                "expected_cents": current["total_cents"],
                "expected_revision": current["revision"],
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/statements/"
            + old["id"]
            + "/reopen?expected_revision="
            + old["revision"]
        ).status_code
        == 409
    )
    closed = statement(client)
    assert (
        client.post(
            "/api/statements/"
            + old["id"]
            + "/reopen?expected_revision="
            + closed["revision"]
        ).status_code
        == 200
    )


def test_revision_stable_and_invalid_token_rejected(client, login):
    _, card = setup(client, login)
    buy(client, card)
    s = statement(client)
    assert statement(client)["revision"] == s["revision"]
    assert (
        client.post(
            "/api/statements/" + s["id"] + "/close",
            json={"expected_cents": s["total_cents"], "expected_revision": "invalid"},
        ).status_code
        == 422
    )
