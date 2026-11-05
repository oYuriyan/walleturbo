"""Somente em banco de desenvolvimento: cria e remove um banco temporário próprio."""

import os
import json
from datetime import date
import tempfile
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from sqlalchemy import create_engine, text
from app import migrate
from app.db import engine

if os.environ.get("WALLETURBO_INTEGRATION") != "1":
    raise RuntimeError("Exige WALLETURBO_INTEGRATION=1 em ambiente de testes")

name = "walleturbo_migration_test_" + uuid4().hex
admin_url = engine.url.set(
    drivername="postgresql", database="postgres"
).render_as_string(hide_password=False)
test_engine = create_engine(engine.url.set(database=name))
with psycopg.connect(admin_url, autocommit=True) as admin:
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
try:
    with test_engine.begin() as conn:
        conn.connection.driver_connection.execute(
            (migrate.DIRECTORY / "001_initial.sql").read_text()
        )
        conn.execute(
            text(
                "INSERT INTO goals(id,owner,name,target_cents,saved_cents,deadline) VALUES ('legacy-goal','synthetic','Meta preservada',50000,1000,'2027-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO transactions(id,owner,date,description,amount_cents,kind,category,reviewed) VALUES ('preserved','synthetic','2026-11-01','Legado',1234,'expense','Outros',true)"
            )
        )
    migrate.engine = test_engine
    try:
        migrate.migrate()
        raise AssertionError("Adoção implícita indevida")
    except RuntimeError as exc:
        assert "legado" in str(exc)
    original = migrate.DIRECTORY
    with tempfile.TemporaryDirectory() as legacy_dir:
        migrate.DIRECTORY = Path(legacy_dir)
        for file in sorted(original.glob("*.sql"))[:7]:
            (migrate.DIRECTORY / file.name).write_bytes(file.read_bytes())
        migrate.migrate(adopt_initial=True)
        with test_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO accounts(id,owner,name) VALUES ('legacy-account','synthetic','Conta preservada')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO cards(id,owner,name,due_day) VALUES ('legacy-card','synthetic','Cartão preservado',10)"
                )
            )
            conn.execute(
                text(
                    "UPDATE transactions SET account_id='legacy-account' WHERE id='preserved'"
                )
            )
        with test_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO statements(id,owner,card_id,month,due_date,status) VALUES ('legacy-statement','synthetic','legacy-card','2026-11','2026-11-10','open')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO card_charges(id,owner,statement_id,date,description,amount_cents,kind,category,reviewed,operation_id,payload_hash,installment,installments) VALUES ('legacy-charge','synthetic','legacy-statement','2026-11-01','Preservada',1234,'expense','Outros',true,'11111111-1111-4111-8111-111111111111',repeat('a',64),1,1)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO statement_payments(id,owner,statement_id,account_id,date,amount_cents,request_id,payload_hash) VALUES ('legacy-payment','synthetic','legacy-statement','legacy-account','2026-11-02',100,'22222222-2222-4222-8222-222222222222',repeat('b',64))"
                )
            )
            for entity, state in (
                (
                    "card_charge",
                    {"operation_id": "33333333-3333-4333-8333-333333333333"},
                ),
                (
                    "statement_payment",
                    {
                        "id": "deleted-payment",
                        "request_id": "44444444-4444-4444-8444-444444444444",
                    },
                ),
                (
                    "card_charge",
                    {"operation_id": "11111111-1111-4111-8111-111111111111"},
                ),
            ):
                conn.execute(
                    text(
                        'INSERT INTO financial_audit(id,owner,entity,entity_id,action,occurred_at,"before") VALUES (:id,:owner,:entity,:entity_id,:action,:at,CAST(:state AS JSON))'
                    ),
                    {
                        "id": str(uuid4()),
                        "owner": "synthetic",
                        "entity": entity,
                        "entity_id": "legacy",
                        "action": "deleted",
                        "at": "2026-11-01T00:00:00.000000+00:00",
                        "state": json.dumps(state),
                    },
                )
            conn.execute(
                text(
                    "UPDATE transactions SET import_key=repeat('d',64) WHERE id='preserved'"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO card_charges(id,owner,statement_id,date,description,amount_cents,kind,category,reviewed,operation_id,payload_hash,installment,installments,import_key) VALUES ('legacy-imported-charge','synthetic','legacy-statement','2026-11-01','Importado',2000,'expense','Outros',false,'55555555-5555-4555-8555-555555555555',repeat('c',64),1,1,repeat('c',64))"
                )
            )
        migrate.DIRECTORY = original
    migrate.migrate()
    migrate.migrate()
    with test_engine.connect() as conn:
        assert conn.execute(
            text(
                "SELECT amount_cents,account_id FROM transactions WHERE id='preserved'"
            )
        ).one() == (1234, "legacy-account")
        assert (
            conn.execute(text("SELECT count(*) FROM schema_migrations")).scalar() == 11
        )
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM opening_balances")).scalar() == 0
        assert (
            conn.execute(
                text("SELECT name FROM accounts WHERE id='legacy-account'")
            ).scalar()
            == "Conta preservada"
        )
    with test_engine.connect() as conn:
        assert conn.execute(
            text("SELECT archived,version FROM accounts WHERE id='legacy-account'")
        ).one() == (False, 0)
    with test_engine.connect() as conn:
        assert conn.execute(
            text(
                "SELECT name,due_day,archived,version FROM cards WHERE id='legacy-card'"
            )
        ).one() == ("Cartão preservado", 10, False, 0)
    with test_engine.connect() as conn:
        assert conn.execute(
            text(
                "SELECT name,target_cents,saved_cents,archived,version FROM goals WHERE id='legacy-goal'"
            )
        ).one() == ("Meta preservada", 50000, 1000, False, 0)
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM financial_audit")).scalar() == 3
        receipts = conn.execute(
            text(
                "SELECT request_id,cancelled,payload_hash FROM request_receipts ORDER BY request_id"
            )
        ).all()
        assert len(receipts) == 4
        assert [r.cancelled for r in receipts] == [False, False, True, True]
        assert (
            receipts[0].payload_hash == "a" * 64
            and receipts[1].payload_hash == "b" * 64
        )
        assert conn.execute(
            text(
                "SELECT amount_cents,version,correction_reason FROM card_charges WHERE id='legacy-charge'"
            )
        ).one() == (1234, 1, None)
    with test_engine.connect() as conn:
        assert conn.execute(
            text(
                "SELECT amount_cents,account_id,date,version,correction_reason FROM statement_payments WHERE id='legacy-payment'"
            )
        ).one() == (
            100,
            "legacy-account",
            date(2026, 11, 2),
            1,
            None,
        )
    with test_engine.connect() as conn:
        assert conn.execute(
            text(
                "SELECT version,request_id,correction_reason FROM transactions WHERE id='preserved'"
            )
        ).one() == (1, None, None)
        marks = conn.execute(
            text(
                "SELECT scope,source_key,resource_id,removed FROM import_marks ORDER BY scope"
            )
        ).all()
        assert len(marks) == 2 and {m.resource_id for m in marks} == {
            "preserved",
            "legacy-imported-charge",
        }
        assert {m.source_key for m in marks} == {"c" * 64, "d" * 64} and not any(
            m.removed for m in marks
        )
    original = migrate.DIRECTORY
    with tempfile.TemporaryDirectory() as tmp:
        migrate.DIRECTORY = Path(tmp)
        for file in original.glob("*.sql"):
            (migrate.DIRECTORY / file.name).write_bytes(file.read_bytes())
        broken = migrate.DIRECTORY / "012_test_failure.sql"
        broken.write_text(
            "CREATE TABLE must_rollback(id integer); SELECT missing_column;"
        )
        try:
            migrate.migrate()
            raise AssertionError("SQL inválido não foi rejeitado")
        except psycopg.Error:
            pass
        with test_engine.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT to_regclass('public.must_rollback')")
                ).scalar()
                is None
            )
            assert (
                conn.execute(text("SELECT count(*) FROM schema_migrations")).scalar()
                == 11
            )
        broken.unlink()
        with (migrate.DIRECTORY / "001_initial.sql").open("a") as file:
            file.write("-- alteração indevida")
        try:
            migrate.migrate()
            raise AssertionError("Checksum inválido não foi rejeitado")
        except RuntimeError as exc:
            assert "Checksum" in str(exc)
    print(
        "PASS: adoção explícita, preservação do legado, repetição, rollback transacional e checksum de migrações."
    )
finally:
    test_engine.dispose()
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
        )
