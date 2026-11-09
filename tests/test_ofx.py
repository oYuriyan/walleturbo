import json
from pathlib import Path
import pytest
from app.ofx import parse_ofx
from tests.test_balances import account
from tests.test_finance import ENTRY, edit_body

CORPUS = Path(__file__).parent / "fixtures" / "ofx"
SGML = (CORPUS / "bank-102.ofx").read_text()
XML = (CORPUS / "bank-220.ofx").read_text()
BASE = "/api/import/ofx"


def body(acct, content=SGML, **changes):
    return {"account_id": acct, "content": content, "reviewed": True, **changes}


def test_corpus_and_identity_across_sgml_xml_reordering_and_civil_dates():
    expected = json.loads((CORPUS / "expected.json").read_text())
    documents = []
    for name, values in expected.items():
        document = parse_ofx((CORPUS / name).read_text())
        assert document.format == values["format"]
        assert [e.date.isoformat() for e in document.entries] == values["dates"]
        assert [e.amount_cents for e in document.entries] == values["amounts_cents"]
        assert [e.kind for e in document.entries] == values["kinds"]
        assert [e.description for e in document.entries] == values["descriptions"]
        assert len(set(document.identities)) == 3
        assert document.masked_account == "••••1234"
        documents.append(document)
    assert dict(zip(documents[0].identities, documents[0].fingerprints)) == dict(
        zip(documents[1].identities, documents[1].fingerprints)
    )
    near_midnight = parse_ofx(SGML.replace("[-3:BRT]", "[+14:FUT]"))
    assert near_midnight.entries[0].date.isoformat() == "2026-11-03"


@pytest.mark.parametrize(
    "old,new",
    [
        ("SYNTHETIC-001", "SYNTHETIC-002"),
        ("<FITID>SYNTHETIC-001", ""),
        ("<CURDEF>BRL", "<CURDEF>USD"),
        ("<ACCTTYPE>CHECKING", "<ACCTTYPE>CREDITLINE"),
        ("<TRNTYPE>DEBIT", "<TRNTYPE>XFER"),
        ("<TRNTYPE>DEBIT", "<TRNTYPE>PAYMENT"),
        ("<TRNTYPE>DEBIT", "<TRNTYPE>CREDIT"),
        ("<TRNAMT>-12.34", "<TRNAMT>0"),
        ("<TRNAMT>-12.34", "<TRNAMT>-12,34"),
        ("<TRNAMT>-12.34", "<TRNAMT>-12.345"),
        ("<TRNAMT>-12.34", "<TRNAMT>NaN"),
        ("<TRNAMT>-12.34", "<TRNAMT>-1.234e1"),
        ("20261103003000[-3:BRT]", "20260230003000[-3:BRT]"),
        ("20261103003000[-3:BRT]", "20261103253000[-3:BRT]"),
        ("20261103003000[-3:BRT]", "20261103003000[-13:BRT]"),
        ("20261103003000[-3:BRT]", "20261031003000[-3:BRT]"),
        ("<NAME>Mercado", "<CORRECTFITID>old<CORRECTACTION>REPLACE<NAME>Mercado"),
        ("<BANKID>999", "<BANKID>999<BANKID>999"),
        ("<CODE>0", "<CODE>2000"),
        ("</OFX>", ""),
        ("<OFX>", '<!DOCTYPE OFX [<!ENTITY x "unsafe">]><OFX>'),
        ("<NAME>Mercado", "<UNKNOWN>opaque<NAME>Mercado"),
    ],
)
def test_rejects_ambiguous_unsupported_or_invalid_sources(old, new):
    with pytest.raises(ValueError):
        parse_ofx(SGML.replace(old, new, 1))


def test_limits_structure_multiple_accounts_and_entities():
    first = SGML[SGML.index("<STMTTRN>") : SGML.index("</STMTTRN>") + len("</STMTTRN>")]
    for invalid in (
        "Á" * 128001,
        SGML.replace(first, first * 501),
        XML.replace("<OFX>", "<OFX extra='attribute'>"),
        XML.replace("<OFX>", "<OFX xmlns='unsupported'>"),
        XML.replace("<OFX>", "<OFX>" * 25).replace("</OFX>", "</OFX>" * 25),
        XML.replace(
            "</BANKMSGSRSV1>",
            XML[XML.index("<STMTTRNRS>") : XML.index("</STMTTRNRS>") + 12]
            + "</BANKMSGSRSV1>",
        ),
        XML.replace("</NAME>", "&unknown;</NAME>", 1),
        SGML.replace("Mercado", "bad\x00data", 1),
        SGML.replace("Mercado sintético", "bad&#0;data", 1),
        XML.replace("Receita sintética", "bad&#128;data", 1),
        XML.replace('SECURITY="NONE"', 'SECURITY="TYPE1"'),
        XML.replace('VERSION="220"', 'VERSION="999"'),
        XML.replace('encoding="UTF-8"', 'encoding="UTF-16"'),
    ):
        with pytest.raises(ValueError):
            parse_ofx(invalid)


def test_preview_read_only_fitids_keep_equal_purchases_and_survive_corrections_deletion(
    client, login
):
    login()
    acct = account(client)
    request = body(acct)
    before = client.get("/api/privacy/export").json()
    preview = client.post(BASE + "/preview", json=request)
    assert preview.status_code == 200, preview.text
    assert preview.json()["source_account"] == "••••1234"
    assert client.get("/api/privacy/export").json() == before
    assert client.post(BASE + "/confirm", json=request).json() == {
        "created": 3,
        "duplicates": 0,
    }
    assert client.post(BASE + "/confirm", json=body(acct, XML)).json() == {
        "created": 0,
        "duplicates": 3,
    }
    exported = client.get("/api/privacy/export").json()
    expenses = [e for e in exported["transactions"] if e["kind"] == "expense"]
    assert (
        len(expenses) == 2
        and expenses[0]["amount_cents"] == expenses[1]["amount_cents"] == 1234
    )
    assert "SYNTHETIC-" not in json.dumps(exported) and "00001234" not in json.dumps(
        exported
    )
    row = expenses[0]
    changed = client.put(
        "/api/transactions/" + row["id"], json=edit_body(row, amount_cents=5678)
    ).json()
    assert client.post(BASE + "/confirm", json=request).json()["created"] == 0
    assert client.get("/api/transactions/" + row["id"]).json()["amount_cents"] == 5678
    assert (
        client.delete(
            f"/api/transactions/{row['id']}?expected_version={changed['version']}"
        ).status_code
        == 204
    )
    assert client.post(BASE + "/confirm", json=request).json() == {
        "created": 0,
        "duplicates": 3,
        "removed": 1,
    }


def test_source_change_is_atomic_and_can_be_excluded_from_selection(client, login):
    login()
    acct = account(client)
    assert client.post(BASE + "/confirm", json=body(acct)).status_code == 200
    modified = SGML.replace("SYNTHETIC-001", "SYNTHETIC-NEW").replace(
        "2500.00", "2600.00"
    )
    before = client.get("/api/privacy/export").json()
    signal = client.post(BASE + "/preview", json=body(acct, modified)).json()
    assert signal["source_conflicts"] == [1]
    assert client.post(BASE + "/confirm", json=body(acct, modified)).status_code == 409
    assert client.get("/api/privacy/export").json() == before
    result = client.post(
        BASE + "/confirm", json=body(acct, modified, excluded_indices=[1])
    )
    assert result.json() == {"created": 1, "duplicates": 1, "skipped": 1}, result.text


def test_fitid_link_and_unlink_reuse_versions_without_changing_finances(client, login):
    login()
    acct = account(client)
    row = client.post(
        "/api/transactions", json={**ENTRY, "account_id": acct, "description": "Manual"}
    ).json()
    link = {
        "source_index": 0,
        "resource_id": row["id"],
        "expected_version": row["version"],
    }
    request = body(acct, excluded_indices=[1, 2], links=[link])
    assert client.post(BASE + "/confirm", json=request).json()["linked"] == 1
    before = client.get("/api/privacy/export").json()["transactions"]
    release = {
        "content": SGML,
        "account_id": acct,
        "release": {
            **link,
            "expected_origin_version": 1,
            "reason": "Destino incorreto",
        },
    }
    assert client.post(BASE + "/unlink", json=release).json() == {"released": 1}
    assert client.get("/api/privacy/export").json()["transactions"] == before
    assert client.post(BASE + "/confirm", json=request).status_code == 409
    preview = client.post(BASE + "/preview", json=body(acct)).json()
    revised = {
        **request,
        "links": [{**link, "expected_origin_version": preview["origin_versions"][0]}],
    }
    assert client.post(BASE + "/confirm", json=revised).json()["linked"] == 1
    assert client.post(BASE + "/unlink", json=release).status_code == 409
    assert len(client.get("/api/history?entity=import_link").json()["items"]) == 3


def test_owner_account_review_primary_identity_and_privacy(client, login):
    login()
    acct = account(client)
    assert (
        client.post(BASE + "/confirm", json=body(acct, reviewed=False)).status_code
        == 422
    )
    assert client.post(BASE + "/preview", json={"content": SGML}).status_code == 422
    login("bob")
    assert client.post(BASE + "/preview", json=body(acct)).status_code == 404
    login()
    assert client.post(BASE + "/confirm", json=body(acct)).status_code == 200
    origin = client.post(BASE + "/preview", json=body(acct)).json()["known_origins"][0]
    assert not origin["releasable"]
    assert (
        client.post(
            BASE + "/unlink",
            json={
                "content": SGML,
                "account_id": acct,
                "release": {
                    "source_index": 0,
                    "resource_id": origin["resource_id"],
                    "expected_version": origin["target"]["version"],
                    "expected_origin_version": origin["version"],
                    "reason": "Tentar apagar origem",
                },
            },
        ).status_code
        == 409
    )
    assert (
        client.delete(
            "/api/privacy/data", headers={"X-Confirm-Delete": "EXCLUIR"}
        ).status_code
        == 200
    )
    login()
    assert all(not rows for rows in client.get("/api/privacy/export").json().values())
