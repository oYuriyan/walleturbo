"""Somente em banco de desenvolvimento: cria e remove um banco temporário próprio."""

import os
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
        for file in sorted(original.glob("*.sql"))[:3]:
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
            conn.execute(text("SELECT count(*) FROM schema_migrations")).scalar() == 6
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
    original = migrate.DIRECTORY
    with tempfile.TemporaryDirectory() as tmp:
        migrate.DIRECTORY = Path(tmp)
        for file in original.glob("*.sql"):
            (migrate.DIRECTORY / file.name).write_bytes(file.read_bytes())
        broken = migrate.DIRECTORY / "007_test_failure.sql"
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
                == 6
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
