import argparse
import io
import json
import subprocess
import tarfile
import pytest
from scripts import local_backup as recovery


def archive(tmp_path, names):
    target = tmp_path / "archive.tar"
    with tarfile.open(target, "w") as stream:
        for name in names:
            info = tarfile.TarInfo(name)
            info.size = 2
            stream.addfile(info, io.BytesIO(b"{}"))
    return target


@pytest.mark.parametrize(
    "names", [["../outside"], ["/absolute"], [".env", ".env"], ["unknown"]]
)
def test_invalid_archive_names_are_refused_without_traversal(tmp_path, names):
    decoded = tmp_path / "decoded"
    decoded.mkdir()
    with pytest.raises(ValueError):
        recovery.unpack(archive(tmp_path, names), decoded)
    assert not list(decoded.iterdir())


def test_archive_symlinks_are_refused(tmp_path):
    target = tmp_path / "symlink.tar"
    with tarfile.open(target, "w") as stream:
        link = tarfile.TarInfo(".env")
        link.type, link.linkname = tarfile.SYMTYPE, "../secret"
        stream.addfile(link)
    decoded = tmp_path / "decoded"
    decoded.mkdir()
    with pytest.raises(ValueError):
        recovery.unpack(target, decoded)


def test_key_requires_private_regular_file(tmp_path):
    key = tmp_path / "key"
    key.write_text("a" * 64 + "\n")
    key.chmod(0o600)
    assert recovery.key_file(key) == key.resolve()
    alias = tmp_path / "alias"
    alias.symlink_to(key)
    with pytest.raises(ValueError):
        recovery.key_file(alias)
    key.chmod(0o644)
    with pytest.raises(ValueError):
        recovery.key_file(key)


def test_dump_failure_restarts_only_original_writers_and_never_publishes(
    tmp_path, monkeypatch
):
    (tmp_path / ".env").write_text("POSTGRES_PASSWORD=synthetic\n")
    key = tmp_path / "key"
    key.write_text("a" * 64)
    key.chmod(0o600)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if "--services" in command:
            return subprocess.CompletedProcess(command, 0, b"api\ndb\n")
        if "--quiet" in command:
            return subprocess.CompletedProcess(command, 0, b"original-api-id\n")
        if "pg_dump" in command:
            raise RuntimeError("dump failed")
        return subprocess.CompletedProcess(command, 0, b"")

    monkeypatch.setattr(recovery, "run", run)
    args = argparse.Namespace(
        config=tmp_path,
        key=key,
        output=tmp_path / "backup.gpg",
        project="walleturbo",
        finance_only=True,
    )
    with pytest.raises(RuntimeError, match="dump failed"):
        recovery.backup(args)
    assert calls[-1] == ["docker", "start", "original-api-id"]
    assert not args.output.exists()


def test_restore_existing_project_is_never_adopted(monkeypatch):
    monkeypatch.setattr(
        recovery,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, b"existing-volume" if "volume" in command else b""
        ),
    )
    with pytest.raises(ValueError, match="já existe"):
        recovery.existing_project("walleturbo-restore-existing")


def test_runtime_config_uses_recovered_file_and_is_never_overwritten(tmp_path):
    directory = tmp_path / 'recovery with "quotes"'
    directory.mkdir()
    target = recovery.runtime_file(directory)
    assert target.stat().st_mode & 0o077 == 0
    paths = [
        line.split("!override ", 1)[1]
        for line in target.read_text().splitlines()
        if "!override" in line
    ]
    assert len(paths) == 2
    assert all(json.loads(value) == [str(directory / ".env")] for value in paths)
    assert "image: walleturbo-parser" in target.read_text()
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        recovery.runtime_file(directory)
    assert target.read_bytes() == original
