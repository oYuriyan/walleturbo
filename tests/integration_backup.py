"""Ensaio local sintético; nunca restaura sobre o projeto de origem."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import select
import subprocess
import sys
import tempfile
import time
from uuid import uuid4
from scripts import local_backup as recovery

parser = argparse.ArgumentParser()
parser.add_argument("--identity", action="store_true")
parser.add_argument("--promote", action="store_true")
args = parser.parse_args()
if args.promote and not args.identity:
    parser.error("--promote exige --identity e conferência de login pelo navegador")
ROOT = Path(__file__).resolve().parents[1]
script = ROOT / "scripts/local_backup.py"
source = recovery.compose("walleturbo", ROOT, args.identity)
owner = "backup-test-" + uuid4().hex
project = "walleturbo-restore-test-" + uuid4().hex[:10]


def execute(command, **kwargs):
    return subprocess.run(
        command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
    ).stdout


def sql(cmd, service, query):
    database = recovery.DATABASES[service][0]
    return execute(
        cmd
        + ["exec", "-T", service, "psql", "-U", database, "-d", database, "-Atc", query]
    )


def fingerprints(cmd, service):
    tables = (
        sql(
            cmd,
            service,
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename",
        )
        .decode()
        .split()
    )
    if service == "auth-db":
        tables = [
            name
            for name in tables
            if name in ("realm", "user_entity", "credential", "client")
        ]
        assert set(tables) == {"realm", "user_entity", "credential", "client"}
        assert int(sql(cmd, service, "SELECT count(*) FROM credential")) > 0
    output = {}
    for name in tables:
        assert re.fullmatch(r"[a-z_][a-z0-9_]*", name)
        data = sql(
            cmd,
            service,
            f"SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text), '[]'::jsonb) FROM \"{name}\" t",
        )
        output[name] = hashlib.sha256(data).hexdigest()
    return output


# A linha sintética torna a comparação significativa mesmo numa base vazia.
seed = """from datetime import date
from app.main import app
from app.db import Session, Account, Transaction
with Session() as db:
    account = Account(owner=OWNER, name="Conta de restauração sintética")
    db.add(account)
    db.flush()
    db.add(Transaction(owner=OWNER, account_id=account.id, date=date(2026,11,10), description="Despesa de restauração", amount_cents=1250, kind="expense", category="Outros", reviewed=True))
    db.commit()
""".replace("OWNER", repr(owner))
execute(source + ["exec", "-T", "api", "python"], input=seed.encode())
services = ["db", "auth-db"] if args.identity else ["db"]
restored = None
original_writers = []
started = time.monotonic()
try:
    expected = {service: fingerprints(source, service) for service in services}
    with tempfile.TemporaryDirectory(prefix="walleturbo-recovery-test-") as temporary:
        work = Path(temporary)
        key, saved, directory = (
            work / "test.backup-key",
            work / "copy.gpg",
            work / "restored",
        )
        execute([sys.executable, str(script), "keygen", "--key", str(key)])
        command = [
            sys.executable,
            str(script),
            "backup",
            "--key",
            str(key),
            "--output",
            str(saved),
        ]
        if not args.identity:
            command.append("--finance-only")
        execute(command)
        assert saved.stat().st_mode & 0o077 == 0
        assert b"Despesa de restaura" not in saved.read_bytes()
        wrong = work / "wrong.backup-key"
        execute([sys.executable, str(script), "keygen", "--key", str(wrong)])
        base = [
            sys.executable,
            str(script),
            "restore",
            "--project",
            project,
            "--directory",
            str(directory),
        ]
        failed = subprocess.run(
            base + ["--key", str(wrong), "--input", str(saved)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert failed.returncode != 0 and not directory.exists()
        corrupt = work / "corrupt.gpg"
        data = bytearray(saved.read_bytes())
        data[-1] ^= 1
        corrupt.write_bytes(data)
        failed = subprocess.run(
            base + ["--key", str(key), "--input", str(corrupt)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert failed.returncode != 0 and not directory.exists()
        restored = recovery.compose(project, ROOT, args.identity)
        execute(base + ["--key", str(key), "--input", str(saved)])
        restored = recovery.compose(project, directory, args.identity) + [
            "-f",
            str(directory / "runtime.compose.yaml"),
        ]
        actual = {service: fingerprints(restored, service) for service in services}
        assert actual == expected
        manifest = json.loads((directory / "manifest.json").read_text())
        assert manifest["identity"] == args.identity
        assert directory.stat().st_mode & 0o077 == 0
        for name in (".env", ".env.auth") if args.identity else (".env",):
            assert (directory / name).read_bytes() == (ROOT / name).read_bytes()
            assert (directory / name).stat().st_mode & 0o077 == 0
        refused = subprocess.run(
            base + ["--key", str(key), "--input", str(saved)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert refused.returncode != 0
        assert {
            service: fingerprints(restored, service) for service in services
        } == expected
        if args.promote:
            promoted = restored
            probe = uuid4().hex
            with (directory / ".env").open("a") as stream:
                stream.write(f"\nWALLETURBO_RECOVERY_PROBE={probe}\n")
            model = json.loads(execute(promoted + ["config", "--format", "json"]))
            for service in ("api", "migrate"):
                assert (
                    model["services"][service]["environment"][
                        "WALLETURBO_RECOVERY_PROBE"
                    ]
                    == probe
                )
            original_writers = (
                execute(source + ["ps", "--quiet", "api", "keycloak"]).decode().split()
            )
            assert len(original_writers) == 2
            print(
                "RECOVERY: bancos/configurações conferidos; iniciando destino isolado.",
                flush=True,
            )
            execute(["docker", "stop", *original_writers])
            try:
                execute(
                    promoted
                    + [
                        "up",
                        "--no-build",
                        "-d",
                        "--wait",
                        "--wait-timeout",
                        "240",
                        "api",
                    ]
                )
                # Handshake sem arquivos de senha/TOTP: o pai conserva a fixture em memória.
                print("RECOVERY_READY", flush=True)
                readable, _, _ = select.select([sys.stdin], [], [], 120)
                assert readable and sys.stdin.readline().strip() == "VERIFIED"
                print(
                    "PASS: ambiente recuperado iniciado e login/MFA conferido.",
                    flush=True,
                )
            finally:
                try:
                    execute(promoted + ["down", "--volumes"])
                    restored = None
                finally:
                    execute(
                        source
                        + [
                            "start",
                            "--wait",
                            "--wait-timeout",
                            "240",
                            "api",
                            "keycloak",
                        ]
                    )
                    original_writers = []
        # Preservar configs até a limpeza dos volumes sintéticos isolados.
        if restored:
            execute(restored + ["down", "--volumes"])
            restored = None
    running = (
        execute(source + ["ps", "--status", "running", "--services"]).decode().split()
    )
    assert "api" in running and (not args.identity or "keycloak" in running)
    print(
        f"PASS: backup GPG {'financeiro e identidade' if args.identity else 'financeiro'} restaura dados/configurações em projeto novo, recusa chave incorreta/corrupção/destino existente e reativa escritores. Ensaio sintético: {time.monotonic()-started:.1f}s."
    )
finally:
    try:
        if restored:
            execute(restored + ["down", "--volumes"])
    finally:
        if original_writers:
            execute(
                source + ["start", "--wait", "--wait-timeout", "240", "api", "keycloak"]
            )
    # Só remove a conta e o lançamento criados por este ensaio, sem tocar nos demais.
    sql(
        source,
        "db",
        f"DELETE FROM transactions WHERE owner='{owner}'; DELETE FROM financial_audit WHERE owner='{owner}'; DELETE FROM accounts WHERE owner='{owner}';",
    )
