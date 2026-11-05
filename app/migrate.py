"""Migrações PostgreSQL transacionais, com checksum e lock de implantação."""

import argparse
import hashlib
from pathlib import Path
from sqlalchemy import inspect, text
from app.db import engine

DIRECTORY = Path(__file__).parent / "migrations"


def migrate(adopt_initial=False):
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Migrações de produção exigem PostgreSQL")
    files = sorted(DIRECTORY.glob("[0-9][0-9][0-9]_*.sql"))
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(824107219)"))
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())"
            )
        )
        versions = dict(
            conn.execute(text("SELECT version, checksum FROM schema_migrations")).all()
        )
        known = {p.name for p in files}
        if set(versions) - known:
            raise RuntimeError(
                "Banco possui migrações mais recentes que esta aplicação"
            )
        existing = set(inspect(conn).get_table_names())
        if not versions and {"transactions", "goals"} & existing:
            expected = {
                "transactions": {
                    "id",
                    "owner",
                    "date",
                    "description",
                    "amount_cents",
                    "kind",
                    "category",
                    "reviewed",
                    "import_key",
                },
                "goals": {
                    "id",
                    "owner",
                    "name",
                    "target_cents",
                    "saved_cents",
                    "deadline",
                },
            }
            if not adopt_initial:
                raise RuntimeError(
                    "Banco legado detectado. Faça backup e execute --adopt-initial para reconhecer a versão 0.1"
                )
            for table, columns in expected.items():
                if (
                    table not in existing
                    or {c["name"] for c in inspect(conn).get_columns(table)} != columns
                ):
                    raise RuntimeError("Schema legado divergente; adoção recusada")
            baseline = files[0]
            digest = hashlib.sha256(baseline.read_bytes()).hexdigest()
            conn.execute(
                text("INSERT INTO schema_migrations(version, checksum) VALUES (:v,:c)"),
                {"v": baseline.name, "c": digest},
            )
            versions[baseline.name] = digest
        for file in files:
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            if file.name in versions:
                if versions[file.name] != digest:
                    raise RuntimeError(
                        f"Checksum divergente: {file.name}. Não altere migrações aplicadas"
                    )
                continue
            # SQL somente de arquivos versionados; sem concatenação de entrada externa.
            conn.connection.driver_connection.execute(file.read_text())
            conn.execute(
                text("INSERT INTO schema_migrations(version, checksum) VALUES (:v,:c)"),
                {"v": file.name, "c": digest},
            )
            print(f"Migração aplicada: {file.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--adopt-initial", action="store_true")
    migrate(parser.parse_args().adopt_initial)
