import json
from pathlib import Path
import re
import pytest
from sqlalchemy import event
from app.db import FinancialAudit
from app.ofx import parse_ofx
from tests.test_cards import setup, buy, delete_operation
from tests.test_corrections import correction

CORPUS = Path(__file__).parent / "fixtures" / "ofx"
SGML = (CORPUS / "card-102.ofx").read_text()
XML = (CORPUS / "card-220.ofx").read_text()


def prepare(client, login):
    _, card = setup(client, login)
    bills = [
        client.post(f"/api/cards/{card['id']}/statements?month={month}").json()
        for month in ("2026-11", "2026-12")
    ]
    return card, bills[0], bills[1]


def path(bill):
    return f"/api/statements/{bill['id']}/import/ofx"


def body(content=SGML, **changes):
    return {"content": content, "reviewed": True, "credits_reviewed": True, **changes}


def test_card_corpus_credit_payment_privacy_and_identity_between_formats():
    expected = json.loads((CORPUS / "card-expected.json").read_text())
    sources = []
    for name, value in expected.items():
        document = parse_ofx((CORPUS / name).read_text(), card=True)
        assert [entry.date.isoformat() for entry in document.entries] == value["dates"]
        assert [entry.amount_cents for entry in document.entries] == value[
            "amounts_cents"
        ]
        assert [entry.kind for entry in document.entries] == value["kinds"]
        assert [entry["amount_cents"] for entry in document.payments] == value[
            "payment_amounts_cents"
        ]
        assert (
            sum(
                e.amount_cents * (-1 if e.kind == "refund" else 1)
                for e in document.entries
            )
            == value["net_charges_cents"]
        )
        assert "4111 1111 1111 1111" not in str(document.entries) + str(
            document.payments
        )
        assert document.masked_account == "••••1111"
        assert len(set(document.identities)) == 3
        sources.append(dict(zip(document.identities, document.fingerprints)))
    assert sources[0] == sources[1]


@pytest.mark.parametrize(
    "old,new",
    [
        ("CARD-PAY", "CARD-001"),
        ("<TRNAMT>20.00", "<TRNAMT>-20.00"),
        ("<TRNAMT>50.00", "<TRNAMT>-50.00"),
        ("<TRNTYPE>DEBIT", "<TRNTYPE>DEP"),
        ("<CURDEF>BRL", "<CURDEF>USD"),
        ("<FI><ORG>Emissor sintético<FID>999</FI>", ""),
    ],
)
def test_card_rejects_invalid_sign_type_issuer_currency_and_duplicate_payment_id(
    old, new
):
    with pytest.raises(ValueError):
        parse_ofx(SGML.replace(old, new, 1), card=True)


def test_bank_and_card_documents_cannot_be_mixed_or_sent_to_wrong_reader():
    with pytest.raises(ValueError):
        parse_ofx(SGML)
    with pytest.raises(ValueError):
        parse_ofx((CORPUS / "bank-102.ofx").read_text(), card=True)
    mixed = SGML.replace(
        "</OFX>",
        "<BANKMSGSRSV1><STMTTRNRS><STATUS><CODE>0</STATUS></STMTTRNRS></BANKMSGSRSV1></OFX>",
    )
    with pytest.raises(ValueError):
        parse_ofx(mixed, card=True)


def test_preview_read_only_import_preserves_twins_and_does_not_create_payments_or_future_parcels(
    client, login
):
    _, bill, other = prepare(client, login)
    before = client.get("/api/privacy/export").json()
    preview = client.post(path(bill) + "/preview", json=body())
    assert preview.status_code == 200, preview.text
    assert len(preview.json()["entries"]) == 3 and len(preview.json()["payments"]) == 1
    assert (
        "4111111111111111" not in preview.text
        and "4111 1111 1111 1111" not in preview.text
    )
    assert client.get("/api/privacy/export").json() == before
    assert client.post(path(bill) + "/confirm", json=body()).json() == {
        "created": 3,
        "duplicates": 0,
    }
    assert client.post(path(bill) + "/confirm", json=body(XML)).json() == {
        "created": 0,
        "duplicates": 3,
    }
    exported = client.get("/api/privacy/export").json()
    assert len(exported["card_charges"]) == 3 and len(exported["statements"]) == 2
    assert not exported["statement_payments"] and not exported["transactions"]
    assert all(
        row["installment"] == row["installments"] == 1
        for row in exported["card_charges"]
    )
    assert "4111111111111111" not in json.dumps(
        exported
    ) and "4111 1111 1111 1111" not in json.dumps(exported)
    assert client.get(f"/api/statements/{bill['id']}").json()["total_cents"] == 22690
    assert client.get(f"/api/statements/{other['id']}").json()["total_cents"] == 0


def test_selected_credits_require_explicit_refund_review(client, login):
    _, bill, _ = prepare(client, login)
    before = client.get("/api/privacy/export").json()
    assert (
        client.post(path(bill) + "/confirm", json=body(reviewed=False)).status_code
        == 422
    )
    assert (
        client.post(
            path(bill) + "/confirm", json=body(credits_reviewed=False)
        ).status_code
        == 422
    )
    assert client.get("/api/privacy/export").json() == before
    assert client.post(
        path(bill) + "/confirm", json=body(credits_reviewed=False, excluded_indices=[1])
    ).json() == {"created": 2, "duplicates": 0, "skipped": 1}


def test_payment_only_preview_cannot_create_financial_entries(client, login):
    _, bill, _ = prepare(client, login)
    payments_only = re.sub(
        r"<STMTTRN>.*?</STMTTRN>",
        lambda match: match[0] if "<TRNTYPE>PAYMENT" in match[0] else "",
        SGML,
        flags=re.DOTALL,
    )
    before = client.get("/api/privacy/export").json()
    preview = client.post(path(bill) + "/preview", json=body(payments_only))
    assert preview.status_code == 200, preview.text
    assert preview.json()["entries"] == [] and len(preview.json()["payments"]) == 1
    assert (
        client.post(path(bill) + "/confirm", json=body(payments_only)).status_code
        == 422
    )
    assert client.get("/api/privacy/export").json() == before


def test_same_fitid_cannot_move_to_other_statement_even_after_deletion(client, login):
    _, bill, other = prepare(client, login)
    assert client.post(path(bill) + "/confirm", json=body()).status_code == 200
    before = client.get("/api/privacy/export").json()
    preview = client.post(path(other) + "/preview", json=body(XML)).json()
    assert preview["context_conflicts"] == [0, 1, 2]
    assert client.post(path(other) + "/confirm", json=body(XML)).status_code == 409
    assert client.get("/api/privacy/export").json() == before
    for row in before["card_charges"]:
        assert (
            delete_operation(
                client, "/api/card-operations/" + row["operation_id"]
            ).status_code
            == 204
        )
    assert client.post(path(bill) + "/confirm", json=body()).json()["removed"] == 3
    assert client.post(path(other) + "/confirm", json=body()).status_code == 409
    assert client.get("/api/privacy/export").json()["card_charges"] == []


def test_signature_conflict_rolls_back_new_sources_and_statement_reservations(
    client, login
):
    _, bill, other = prepare(client, login)
    assert client.post(path(bill) + "/confirm", json=body()).status_code == 200
    modified = SGML.replace("CARD-003", "NEW-SOURCE").replace(
        "<TRNAMT>20.00", "<TRNAMT>25.00"
    )
    before = client.get("/api/privacy/export").json()
    assert client.post(path(bill) + "/preview", json=body(modified)).json()[
        "source_conflicts"
    ] == [1]
    assert client.post(path(bill) + "/confirm", json=body(modified)).status_code == 409
    assert client.get("/api/privacy/export").json() == before
    assert (
        client.post(
            path(other) + "/confirm", json=body(modified, excluded_indices=[0, 1])
        ).json()["created"]
        == 1
    )


def test_link_correction_deletion_and_unlink_keep_origin_and_statement(client, login):
    card, bill, other = prepare(client, login)
    purchase, original = buy(
        client, card, date="2026-11-03", amount_cents=12345, installments=1
    )
    row = purchase.json()[0]
    link = {
        "source_index": 0,
        "resource_id": row["id"],
        "expected_version": row["version"],
    }
    request = body(excluded_indices=[1, 2], links=[link])
    assert client.post(path(bill) + "/confirm", json=request).json()["linked"] == 1
    changed = client.put(
        "/api/card-operations/" + original["request_id"],
        json=correction(client, original, amount_cents=14000),
    )
    assert changed.status_code == 200, changed.text
    assert client.post(path(bill) + "/confirm", json=request).json()["created"] == 0
    current = changed.json()["charges"][0]
    release = {
        "content": SGML,
        "release": {
            **link,
            "expected_version": current["version"],
            "expected_origin_version": 1,
            "reason": "Destino incorreto",
        },
    }
    assert client.post(path(bill) + "/unlink", json=release).status_code == 200
    assert (
        client.post(
            path(other) + "/confirm", json=body(excluded_indices=[1, 2])
        ).status_code
        == 409
    )
    assert client.post(path(bill) + "/confirm", json=request).status_code == 409
    # Um destino compatível pode ser escolhido na nova prévia; não restaura o alvo corrigido.
    new, _ = buy(client, card, date="2026-11-03", amount_cents=12345, installments=1)
    target = new.json()[0]
    revised = body(
        excluded_indices=[1, 2],
        links=[
            {
                **link,
                "resource_id": target["id"],
                "expected_version": target["version"],
                "expected_origin_version": 2,
            }
        ],
    )
    assert client.post(path(bill) + "/confirm", json=revised).json()["linked"] == 1
    assert (
        delete_operation(
            client, "/api/card-operations/" + target["operation_id"]
        ).status_code
        == 204
    )
    assert (
        client.post(path(bill) + "/confirm", json=body(excluded_indices=[1, 2])).json()[
            "removed"
        ]
        == 1
    )
    assert (
        client.get("/api/privacy/export").json()["card_charges"][0]["amount_cents"]
        == 14000
    )


@pytest.mark.parametrize("problem", ["owner", "closed", "archived"])
def test_owner_and_statement_lifecycle_guard_card_ofx(client, login, problem):
    card, bill, _ = prepare(client, login)
    if problem == "owner":
        login("bob")
    elif problem == "closed":
        current = client.get(f"/api/statements/{bill['id']}").json()
        assert (
            client.post(
                f"/api/statements/{bill['id']}/close",
                json={"expected_cents": 0, "expected_revision": current["revision"]},
            ).status_code
            == 200
        )
    else:
        result = client.put(
            "/api/cards/" + card["id"],
            json={
                "name": card["name"],
                "archived": True,
                "expected_version": card["version"],
            },
        )
        assert result.status_code == 200, result.text
    before = client.get("/api/privacy/export").json()
    for action in ("preview", "confirm"):
        assert client.post(path(bill) + "/" + action, json=body()).status_code in (
            404,
            409,
        )
    assert client.get("/api/privacy/export").json() == before


def test_history_failure_releases_all_origin_reservations_and_privacy_covers_receipts(
    client, login
):
    card, bill, other = prepare(client, login)
    purchase, _ = buy(
        client, card, date="2026-11-03", amount_cents=12345, installments=1
    )
    row = purchase.json()[0]
    request = body(
        excluded_indices=[1, 2],
        links=[
            {
                "source_index": 0,
                "resource_id": row["id"],
                "expected_version": row["version"],
            }
        ],
    )
    before = client.get("/api/privacy/export").json()

    def fail(mapper, connection, target):
        if target.entity == "import_link":
            raise RuntimeError("histórico indisponível")

    event.listen(FinancialAudit, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="histórico indisponível"):
            client.post(path(bill) + "/confirm", json=request)
    finally:
        event.remove(FinancialAudit, "before_insert", fail)
    assert client.get("/api/privacy/export").json() == before
    assert client.post(path(other) + "/confirm", json=body()).json()["created"] == 3
    assert (
        client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        ).status_code
        == 200
    )
    login()
    assert all(
        not values for values in client.get("/api/privacy/export").json().values()
    )
