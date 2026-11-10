"""Backup GPG e restauração PostgreSQL em projeto Compose novo e isolado."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DATABASES = {
    "db": ("walleturbo", "finance.dump"),
    "auth-db": ("keycloak", "identity.dump"),
}


def run(command, **kwargs):
    try:
        return subprocess.run(command, check=True, stderr=subprocess.PIPE, **kwargs)
    except subprocess.CalledProcessError:
        raise RuntimeError(
            f"Falha em {Path(command[0]).name}; operação interrompida. Consulte o procedimento de recuperação."
        ) from None


def compose(project, directory, identity):
    cmd = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--env-file",
        str(directory / ".env"),
    ]
    if identity:
        cmd += ["--env-file", str(directory / ".env.auth")]
    cmd += ["-f", str(ROOT / "compose.yaml")]
    if identity:
        cmd += ["-f", str(ROOT / "compose.auth.yaml")]
    return cmd


def key_file(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError(
            "A chave deve ser arquivo regular privado (chmod 600), sem symlink."
        )
    if not re.fullmatch(rb"[a-f0-9]{64}\n?", path.read_bytes()):
        raise ValueError("Chave inválida. Use o subcomando keygen.")
    return path.resolve()


@contextmanager
def gpg_home():
    with tempfile.TemporaryDirectory(prefix="walleturbo-gpg-") as temporary:
        home = Path(temporary)
        try:
            yield [
                "gpg",
                "--homedir",
                str(home),
                "--batch",
                "--no-tty",
                "--pinentry-mode",
                "loopback",
                "--no-symkey-cache",
            ]
        finally:
            subprocess.run(
                ["gpgconf", "--homedir", str(home), "--kill", "gpg-agent"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def existing_project(project):
    # Não adotar containers parados, volumes ou redes de outra tentativa.
    for resource in ("container", "volume", "network"):
        result = run(
            [
                "docker",
                resource,
                "ls",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={project}",
            ],
            stdout=subprocess.PIPE,
        )
        if result.stdout.strip():
            raise ValueError(
                "O projeto de destino já existe. Escolha outro nome; nenhum dado será sobrescrito."
            )


def backup(args):
    identity = not args.finance_only
    configs = [".env", ".env.auth"] if identity else [".env"]
    for name in configs:
        path = args.config / name
        if not path.is_file() or path.stat().st_size > 1_000_000:
            raise ValueError(f"Configuração necessária ausente ou inválida: {name}")
    key = key_file(args.key)
    output = args.output.resolve()
    if output.exists():
        raise ValueError("O arquivo de saída já existe; preservado.")
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = compose(args.project, args.config, identity)
    running = (
        run(cmd + ["ps", "--status", "running", "--services"], stdout=subprocess.PIPE)
        .stdout.decode()
        .split()
    )
    services = list(DATABASES) if identity else ["db"]
    if any(service not in running for service in services):
        raise ValueError(
            "Bancos necessários não estão em execução. Backup financeiro isolado exige --finance-only explícito."
        )
    writers = [service for service in ("api", "keycloak") if service in running]
    if args.finance_only and "auth-db" in running:
        raise ValueError(
            "Identidade ativa: faça backup completo para preservar os dois bancos."
        )
    writer_ids = []
    for service in writers:
        writer_ids.extend(
            run(cmd + ["ps", "--all", "--quiet", service], stdout=subprocess.PIPE)
            .stdout.decode()
            .split()
        )
    # O diretório privado contém dumps temporários sem criptografia; nunca é versionado.
    with tempfile.TemporaryDirectory(prefix="walleturbo-backup-") as temporary:
        temp = Path(temporary)
        stopped = False
        try:
            if writers:
                stopped = True
                run(cmd + ["stop", *writers], stdout=subprocess.DEVNULL)
            started = datetime.now(timezone.utc).isoformat()
            files = []
            for service in services:
                database, name = DATABASES[service]
                target = temp / name
                with target.open("xb") as stream:
                    os.chmod(target, 0o600)
                    run(
                        cmd
                        + [
                            "exec",
                            "-T",
                            service,
                            "pg_dump",
                            "-U",
                            database,
                            "-d",
                            database,
                            "--format=custom",
                            "--no-owner",
                            "--no-privileges",
                        ],
                        stdout=stream,
                    )
                files.append(name)
            for name in configs:
                shutil.copyfile(args.config / name, temp / name)
                os.chmod(temp / name, 0o600)
                files.append(name)
            manifest = {
                "format": 1,
                "identity": identity,
                "started_at": started,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "git_commit": run(
                    ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                    stdout=subprocess.PIPE,
                )
                .stdout.decode()
                .strip(),
                "files": {name: digest(temp / name) for name in files},
            }
            (temp / "manifest.json").write_text(json.dumps(manifest, indent=2))
        finally:
            if stopped:
                # Reinicia os mesmos containers; não recria dependências nem volumes.
                run(["docker", "start", *writer_ids], stdout=subprocess.DEVNULL)
        with gpg_home() as gpg:
            encrypted = temp / "backup.gpg"
            process = subprocess.Popen(
                gpg
                + [
                    "--passphrase-file",
                    str(key),
                    "--symmetric",
                    "--cipher-algo",
                    "AES256",
                    "--output",
                    str(encrypted),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
                    for name in ["manifest.json", *files]:
                        archive.add(temp / name, arcname=name, recursive=False)
                process.stdin.close()
                if process.wait() != 0:
                    raise RuntimeError("Criptografia falhou; backup não publicado.")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            # Publicação sem sobrescrever um arquivo criado por outra operação.
            partial = output.parent / (".walleturbo-" + secrets.token_hex(12))
            try:
                with partial.open("xb") as stream:
                    os.chmod(partial, 0o600)
                    with encrypted.open("rb") as source:
                        shutil.copyfileobj(source, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.link(partial, output)
            finally:
                partial.unlink(missing_ok=True)
    print(
        "Backup criptografado criado. Preserve a chave separadamente e teste a restauração."
    )


def unpack(archive, destination):
    with tarfile.open(archive, "r:") as source:
        members = source.getmembers()
        names = [item.name for item in members]
        allowed = {
            "manifest.json",
            ".env",
            ".env.auth",
            "finance.dump",
            "identity.dump",
        }
        if (
            len(names) != len(set(names))
            or set(names) - allowed
            or any(not item.isfile() or item.size > 2_000_000_000 for item in members)
        ):
            raise ValueError("Arquivo de recuperação inválido.")
        for member in members:
            with (
                source.extractfile(member) as incoming,
                (destination / member.name).open("xb") as outgoing,
            ):
                os.chmod(destination / member.name, 0o600)
                shutil.copyfileobj(incoming, outgoing)
    manifest = json.loads((destination / "manifest.json").read_text())
    if manifest.get("format") != 1 or type(manifest.get("identity")) is not bool:
        raise ValueError("Formato de backup incompatível.")
    expected = {".env", "finance.dump"} | (
        {".env.auth", "identity.dump"} if manifest["identity"] else set()
    )
    if set(names) != expected | {"manifest.json"} or set(manifest["files"]) != expected:
        raise ValueError("Backup incompleto.")
    if any(digest(destination / name) != manifest["files"][name] for name in expected):
        raise ValueError("Integridade do backup inválida.")
    return manifest


def restore(args):
    if not re.fullmatch(r"walleturbo-restore-[a-z0-9][a-z0-9-]{0,39}", args.project):
        raise ValueError("Destino exige prefixo walleturbo-restore- e um nome novo.")
    key = key_file(args.key)
    if args.directory.exists():
        raise ValueError("Diretório de recuperação já existe; preservado.")
    existing_project(args.project)
    with tempfile.TemporaryDirectory(prefix="walleturbo-restore-") as temporary:
        temp = Path(temporary)
        plain = temp / "archive.tar"
        with gpg_home() as gpg:
            run(
                gpg
                + [
                    "--passphrase-file",
                    str(key),
                    "--output",
                    str(plain),
                    "--decrypt",
                    str(args.input.resolve()),
                ],
                stdout=subprocess.DEVNULL,
            )
        decoded = temp / "decoded"
        decoded.mkdir(mode=0o700)
        manifest = unpack(plain, decoded)
        # Só cria o diretório durável após autenticar e verificar toda a cópia.
        args.directory.mkdir(mode=0o700, parents=False)
        for path in decoded.iterdir():
            shutil.copyfile(path, args.directory / path.name)
            os.chmod(args.directory / path.name, 0o600)
    cmd = compose(args.project, args.directory.resolve(), manifest["identity"])
    services = list(DATABASES) if manifest["identity"] else ["db"]
    run(
        cmd + ["up", "--no-deps", "-d", "--wait", "--wait-timeout", "120", *services],
        stdout=subprocess.DEVNULL,
    )
    for service in services:
        database, name = DATABASES[service]
        count = run(
            cmd
            + [
                "exec",
                "-T",
                service,
                "psql",
                "-U",
                database,
                "-d",
                database,
                "-Atc",
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'",
            ],
            stdout=subprocess.PIPE,
        ).stdout.strip()
        if count != b"0":
            raise ValueError("Banco de destino não está vazio; restauração recusada.")
        with (args.directory / name).open("rb") as stream:
            run(
                cmd
                + [
                    "exec",
                    "-T",
                    service,
                    "pg_restore",
                    "-U",
                    database,
                    "-d",
                    database,
                    "--exit-on-error",
                    "--no-owner",
                    "--no-privileges",
                ],
                stdin=stream,
                stdout=subprocess.DEVNULL,
            )
    print(
        "Bancos restaurados em projeto isolado. API e identidade não foram iniciadas. Confira os dados antes de promover o ambiente."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    key = sub.add_parser("keygen", help="Gerar chave privada em arquivo novo")
    key.add_argument("--key", type=Path, required=True)
    save = sub.add_parser(
        "backup", help="Capturar bancos e configurações com criptografia GPG"
    )
    save.add_argument("--project", default="walleturbo")
    save.add_argument("--config", type=Path, default=ROOT)
    save.add_argument("--key", type=Path, required=True)
    save.add_argument("--output", type=Path, required=True)
    save.add_argument("--finance-only", action="store_true")
    load = sub.add_parser(
        "restore", help="Restaurar em projeto novo, sem portas ou serviços de aplicação"
    )
    load.add_argument("--project", required=True)
    load.add_argument("--directory", type=Path, required=True)
    load.add_argument("--key", type=Path, required=True)
    load.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.action == "keygen":
            with args.key.open("x") as stream:
                os.chmod(args.key, 0o600)
                stream.write(secrets.token_hex(32) + "\n")
            print("Chave criada. Guarde-a fora do Git e separada do backup.")
        elif args.action == "backup":
            backup(args)
        else:
            restore(args)
    except (OSError, ValueError, RuntimeError, tarfile.TarError, KeyError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
