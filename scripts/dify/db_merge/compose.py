"""
Talk to Dify's Postgres through ``docker compose exec``.

The standard compose file does not publish port 5432, so dump and merge
run inside the ``db_postgres`` container.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import BinaryIO

from scripts.dify.db_merge.envfile import parse_env_file
from scripts.dify.db_merge.models import ComposeError, ComposeTarget, PlanError

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")
_DUMP_MAGIC = b"PGDMP"
_COMPOSE_NAMES = ("docker-compose.yaml", "docker-compose.yml")
_DB_SERVICES = ("db_postgres", "db")


def load_stack(compose_dir: Path, project_name: str) -> ComposeTarget:
    """Load the compose file and database name. Does not contact Docker."""
    directory = compose_dir.expanduser().resolve()
    if not directory.is_dir():
        raise PlanError(f"compose directory not found: {directory}")
    compose_file = _compose_file(directory)
    env_path = directory / ".env"
    if not env_path.is_file():
        raise PlanError(f"no .env next to {compose_file.name}")
    try:
        env = parse_env_file(env_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise PlanError(f"cannot read {env_path}: {exc}") from exc
    db_user = env.get("DB_USERNAME") or "postgres"
    db_name = env.get("DB_DATABASE") or "dify"
    _require_ident(db_user, "DB_USERNAME")
    _require_ident(db_name, "DB_DATABASE")
    project = project_name.strip()
    if project:
        _require_token(project, "project name")
    return ComposeTarget(
        compose_dir=directory,
        compose_file=compose_file,
        project_name=project,
        db_user=db_user,
        db_name=db_name,
        service="",
    )


def bind_service(target: ComposeTarget, service: str | None, timeout: int) -> ComposeTarget:
    """Pick the running Postgres service (``db_postgres`` on current Dify)."""
    requested = (service or "").strip()
    if requested:
        _require_token(requested, "service")
    chosen = pick_db_service(running_services(target, timeout), requested or None)
    return replace(target, service=chosen)


def pick_db_service(running: list[str], requested: str | None) -> str:
    """Choose ``db_postgres`` or the older ``db`` service."""
    names = {line.strip() for line in running if line.strip()}
    if requested:
        if requested not in names:
            visible = ", ".join(sorted(names)) or "(none)"
            raise ComposeError(f"service {requested} is not running; running: {visible}")
        return requested
    found = [name for name in _DB_SERVICES if name in names]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        raise ComposeError("both db_postgres and db are running")
    raise ComposeError("Postgres is not running. Start the Dify stack, then retry.")


def run_docker(args: list[str], timeout: int) -> bytes:
    """Run ``docker`` and return stdout."""
    out, _err = _run_capture(["docker", *args], None, timeout)
    return out


def compose_stdout(target: ComposeTarget, args: list[str], timeout: int) -> str:
    """Run a compose command and return stdout."""
    out, _err = _run_capture(target.command(args), None, timeout)
    return out.decode("utf-8", errors="replace")


def running_services(target: ComposeTarget, timeout: int) -> list[str]:
    """Service names with a running container in this compose project."""
    out, _err = _run_capture(target.command(["ps", "--services", "--status", "running"]), None, timeout)
    text = out.decode("utf-8", errors="replace")
    return [line.strip() for line in text.splitlines() if line.strip()]


def run_psql(target: ComposeTarget, sql: str, timeout: int) -> str:
    """Run a script on stdin inside the database container."""
    service = _require_service(target)
    cmd = target.command(
        [
            "exec",
            "-T",
            "-e",
            "PGCLIENTENCODING=UTF-8",
            service,
            "psql",
            "-X",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            target.db_user,
            "-d",
            target.db_name,
            "-f",
            "-",
        ]
    )
    out, _err = _run_capture(cmd, sql.encode("utf-8"), timeout)
    return out.decode("utf-8")


def stream_pg_dump(target: ComposeTarget, dest: Path, timeout: int) -> None:
    """Write a custom-format dump. Deletes ``dest`` if pg_dump fails."""
    service = _require_service(target)
    cmd = target.command(
        [
            "exec",
            "-T",
            "-e",
            "PGCLIENTENCODING=UTF-8",
            service,
            "pg_dump",
            "-U",
            target.db_user,
            "-d",
            target.db_name,
            "-Fc",
            "--no-owner",
            "--no-acl",
        ]
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with dest.open("wb") as handle:
            _stream_into(cmd, handle, timeout)
    except ComposeError:
        dest.unlink(missing_ok=True)
        raise
    if not _has_dump_magic(dest):
        dest.unlink(missing_ok=True)
        raise ComposeError("pg_dump output is not a PostgreSQL custom-format archive")


def _compose_file(directory: Path) -> Path:
    for name in _COMPOSE_NAMES:
        path = directory / name
        if path.is_file():
            return path
    raise PlanError(f"no docker-compose.yaml in {directory}")


def _require_ident(value: str, label: str) -> None:
    if not _IDENT.match(value):
        raise PlanError(f"{label} is not a PostgreSQL identifier")


def _require_token(value: str, label: str) -> None:
    if not _TOKEN.match(value):
        raise PlanError(f"{label} must be a single token")


def _require_service(target: ComposeTarget) -> str:
    if not target.service or any(char.isspace() for char in target.service):
        raise ComposeError("Postgres service is not selected")
    return target.service


def _stream_into(cmd: list[str], handle: BinaryIO, timeout: int) -> None:
    try:
        with subprocess.Popen(cmd, stdout=handle, stderr=subprocess.PIPE) as proc:
            try:
                _wait_proc(proc, timeout)
            finally:
                _stop_proc(proc)
    except FileNotFoundError as exc:
        raise ComposeError("docker was not found on PATH") from exc
    except OSError as exc:
        raise ComposeError(str(exc)) from exc


def _run_capture(cmd: list[str], stdin: bytes | None, timeout: int) -> tuple[bytes, bytes]:
    try:
        with subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
            try:
                return _finish_capture(proc, stdin, timeout)
            finally:
                _stop_proc(proc)
    except FileNotFoundError as exc:
        raise ComposeError("docker was not found on PATH") from exc
    except OSError as exc:
        raise ComposeError(str(exc)) from exc


def _wait_proc(proc: subprocess.Popen[bytes], timeout: int) -> None:
    try:
        _out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ComposeError(f"docker timed out after {timeout}s") from exc
    code = proc.returncode if proc.returncode is not None else 1
    if code != 0:
        raise ComposeError(_error_text(err or b"", b""))


def _finish_capture(proc: subprocess.Popen[bytes], stdin: bytes | None, timeout: int) -> tuple[bytes, bytes]:
    try:
        out, err = proc.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ComposeError(f"docker timed out after {timeout}s") from exc
    out_bytes = out or b""
    err_bytes = err or b""
    code = proc.returncode if proc.returncode is not None else 1
    if code != 0:
        raise ComposeError(_error_text(err_bytes, out_bytes))
    return out_bytes, err_bytes


def _stop_proc(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.kill()
        proc.communicate(timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return


def _error_text(err: bytes, out: bytes) -> str:
    text = err.decode("utf-8", errors="replace").strip()
    if not text:
        text = out.decode("utf-8", errors="replace").strip()
    if len(text) > 2000:
        return text[:2000] + "...(truncated)"
    return text or "docker command failed"


def _has_dump_magic(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(5) == _DUMP_MAGIC
    except OSError as exc:
        raise ComposeError(f"cannot read {path}") from exc
