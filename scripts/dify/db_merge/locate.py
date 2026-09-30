"""
Find the running Dify compose file and check its Postgres data directory.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from scripts.dify.db_merge.compose import bind_service, compose_stdout, load_stack, run_docker, run_psql
from scripts.dify.db_merge.models import ComposeError, ComposeTarget, PlanError

_POSTGRES_DEST = "/var/lib/postgresql"
_QUERY_TIMEOUT = 120
_DOCKER_TIMEOUT = 60
_IDENTITY_SQL = """
COPY (
  SELECT current_database(), current_setting('data_directory')
) TO STDOUT WITH (FORMAT csv);
""".strip()


@dataclass(frozen=True)
class Mount:
    """One container mount from ``docker inspect``."""

    source: str
    destination: str
    mount_type: str
    name: str


@dataclass(frozen=True)
class PgBind:
    """Postgres data volume declared in the compose file."""

    service: str
    host_path: Path | None
    volume_name: str
    destination: str


@dataclass(frozen=True)
class Discovered:
    """A Dify Postgres container tied to a compose file."""

    compose_dir: Path
    compose_file: Path
    project_name: str
    service: str
    container_id: str
    running: bool


@dataclass(frozen=True)
class VerifiedPg:
    """Compose file, host data directory, and live ``data_directory`` agree."""

    target: ComposeTarget
    compose_file: Path
    service: str
    database: str
    host_data: str
    mount_source: str
    mount_dest: str
    data_directory: str


_SKIP_DIRS = frozenset({"volumes", "storage", "data", "node_modules", "logs", "dify-dump", "pgdata"})
_SERVER_ROOT = Path("/root")


def candidate_dify_dirs() -> list[Path]:
    """Dify compose directories under ``/root``, where the stack is installed."""
    found = dify_compose_dirs(_SERVER_ROOT)
    seen = {path.resolve() for path in found}
    override = os.environ.get("DIFY_COMPOSE_DIR", "").strip()
    if not override:
        return found
    extra = Path(override).expanduser()
    if not _dir_has_dify_postgres(extra):
        return found
    resolved = extra.resolve()
    if resolved not in seen:
        found.append(resolved)
    return found


def dify_compose_dirs(root: Path) -> list[Path]:
    """Compose directories under ``root`` that declare a Postgres data volume.

    Search stays shallow (``/root/dify/docker``) and does not walk ``volumes/``,
    so the Postgres data directory is not scanned.
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for directory in _compose_dirs_under(root, 2):
        if not _dir_has_dify_postgres(directory):
            continue
        resolved = directory.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        found.append(resolved)
    found.sort(key=lambda path: (0 if _is_standard_dify(path) else 1, str(path)))
    return found


def default_dump_dir(compose_dir: Path) -> Path:
    """Dump folder next to a ``/root`` install, for example ``/root/dify-dump``."""
    folder = compose_dir.resolve()
    label = _dump_label(folder)
    if _is_under(folder, _SERVER_ROOT):
        return _SERVER_ROOT / label
    return folder.parent / label


def pg_bind_from_compose(text: str, compose_dir: Path) -> PgBind:
    """Read the Postgres service data volume from a compose file."""
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise PlanError("compose file is not a mapping")
    services = loaded.get("services")
    if not isinstance(services, dict):
        raise PlanError("compose file has no services")
    for service_name in ("db_postgres", "db"):
        service = services.get(service_name)
        if not isinstance(service, dict):
            continue
        image = str(service.get("image") or "")
        if service_name == "db" and "postgres" not in image:
            continue
        bind = _bind_for_service(service_name, service, compose_dir)
        if bind is not None:
            return bind
    raise PlanError("compose file has no Postgres data volume")


def mounts_from_inspect(payload: dict[str, object]) -> list[Mount]:
    """Read container mounts. ``payload`` is one ``docker inspect`` object."""
    raw_mounts = payload.get("Mounts")
    if not isinstance(raw_mounts, list):
        return []
    mounts: list[Mount] = []
    for item in raw_mounts:
        if not isinstance(item, dict):
            continue
        mounts.append(
            Mount(
                source=str(item.get("Source") or ""),
                destination=str(item.get("Destination") or ""),
                mount_type=str(item.get("Type") or ""),
                name=str(item.get("Name") or ""),
            )
        )
    return mounts


def discovered_from_inspect(payload: dict[str, object]) -> Discovered | None:
    """Build a stack from one inspect object, or skip a non-Postgres container."""
    config = payload.get("Config")
    if not isinstance(config, dict):
        return None
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        return None
    service = str(labels.get("com.docker.compose.service") or "")
    mounts = mounts_from_inspect(payload)
    image = str(config.get("Image") or "")
    if not _is_postgres_service(service, image, mounts):
        return None
    compose_file = _label_compose_file(labels)
    if compose_file is None or not compose_file.is_file():
        return None
    working = str(labels.get("com.docker.compose.project.working_dir") or "")
    compose_dir = Path(working).expanduser() if working else compose_file.parent
    state = payload.get("State")
    running = isinstance(state, dict) and bool(state.get("Running"))
    container_id = str(payload.get("Id") or "")
    project = str(labels.get("com.docker.compose.project") or "")
    return Discovered(
        compose_dir=compose_dir,
        compose_file=compose_file,
        project_name=project,
        service=service,
        container_id=container_id,
        running=running,
    )


def assert_pg_location(
    bind: PgBind,
    mounts: list[Mount],
    data_directory: str,
    database: str,
    expected_database: str,
) -> Mount:
    """Raise unless the compose volume, container mount, and live data dir agree."""
    if database != expected_database:
        raise PlanError(f"connected database is {database}; .env says {expected_database}")
    mount = _mount_for_destination(bind.destination, mounts)
    if mount is None:
        raise PlanError(f"container has no mount for {bind.destination}")
    _assert_mount_source(bind, mount)
    if not _path_inside(data_directory, mount.destination):
        raise PlanError(f"Postgres data_directory {data_directory} is outside {mount.destination}")
    if not Path(mount.source).is_dir():
        raise PlanError(f"Postgres data directory is not on disk: {mount.source}")
    return mount


def locate_stacks() -> list[Discovered]:
    """Running or stopped Dify Postgres containers, from Docker labels."""
    container_ids: list[str] = []
    for service in ("db_postgres", "db"):
        raw = run_docker(["ps", "-aq", "--filter", f"label=com.docker.compose.service={service}"], _DOCKER_TIMEOUT)
        container_ids.extend(
            line.strip() for line in raw.decode("utf-8", errors="replace").splitlines() if line.strip()
        )
    if not container_ids:
        return []
    try:
        payload = json.loads(run_docker(["inspect", *container_ids], _DOCKER_TIMEOUT))
    except json.JSONDecodeError as exc:
        raise ComposeError("docker inspect was not JSON") from exc
    if not isinstance(payload, list):
        raise ComposeError("docker inspect did not return a list")
    found: list[Discovered] = []
    seen: set[tuple[str, str]] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        row = discovered_from_inspect(item)
        if row is None:
            continue
        key = (str(row.compose_dir), row.service)
        if key in seen:
            continue
        seen.add(key)
        found.append(row)
    return found


def discovered_from_dir(directory: Path) -> Discovered:
    """A compose directory typed by the operator. The container is checked later."""
    folder = directory.expanduser().resolve()
    compose = _compose_path(folder)
    if compose is None:
        raise PlanError(f"no docker-compose.yaml in {folder}")
    return Discovered(
        compose_dir=folder,
        compose_file=compose,
        project_name="",
        service="",
        container_id="",
        running=False,
    )


def verify_stack(found: Discovered) -> VerifiedPg:
    """Open the stack and require the yaml volume to match the live data directory."""
    if found.container_id and not found.running:
        bind = pg_bind_from_compose(_read_text(found.compose_file), found.compose_dir)
        place = bind.host_path if bind.host_path is not None else Path(bind.volume_name)
        raise PlanError(f"Postgres is stopped.\nyaml: {found.compose_file}\ndata: {place}")
    target = bind_service(load_stack(found.compose_dir, found.project_name), found.service or None, _QUERY_TIMEOUT)
    bind = pg_bind_from_compose(_read_text(target.compose_file), target.compose_dir)
    if bind.service != target.service:
        raise PlanError(f"running service is {target.service}; compose Postgres service is {bind.service}")
    container_id = found.container_id or _container_id(target)
    payload = _inspect_one(container_id)
    mounts = mounts_from_inspect(payload)
    database, data_directory = _identity(target)
    mount = assert_pg_location(bind, mounts, data_directory, database, target.db_name)
    host_data = str(bind.host_path) if bind.host_path is not None else bind.volume_name
    return VerifiedPg(
        target=target,
        compose_file=target.compose_file,
        service=target.service,
        database=database,
        host_data=host_data,
        mount_source=mount.source,
        mount_dest=mount.destination,
        data_directory=data_directory,
    )


def _dir_has_dify_postgres(directory: Path) -> bool:
    compose = _compose_path(directory)
    if compose is None:
        return False
    try:
        text = compose.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    if "db_postgres" not in text and "postgres:" not in text:
        return False
    try:
        pg_bind_from_compose(text, directory)
    except PlanError:
        return False
    return True


def _compose_dirs_under(root: Path, depth: int) -> list[Path]:
    found: list[Path] = []
    _collect_compose_dirs(root, depth, found)
    return found


def _collect_compose_dirs(directory: Path, depth: int, found: list[Path]) -> None:
    try:
        if not directory.is_dir() or directory.is_symlink():
            return
    except OSError:
        return
    if _compose_path(directory) is not None:
        found.append(directory)
    if depth <= 0:
        return
    try:
        children = list(directory.iterdir())
    except OSError:
        return
    for child in children:
        if child.name in _SKIP_DIRS or child.name.startswith("."):
            continue
        _collect_compose_dirs(child, depth - 1, found)


def _is_standard_dify(path: Path) -> bool:
    return path.name == "docker" and path.parent.name == "dify"


def _dump_label(folder: Path) -> str:
    name = folder.parent.name if folder.name == "docker" else folder.name
    if name in {"", "root", "docker", "dify"}:
        return "dify-dump"
    return f"{name}-dump"


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _compose_path(directory: Path) -> Path | None:
    for name in ("docker-compose.yaml", "docker-compose.yml"):
        path = directory / name
        if path.is_file():
            return path
    return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PlanError(f"cannot read {path}: {exc}") from exc


def _bind_for_service(service_name: str, service: Mapping[object, object], compose_dir: Path) -> PgBind | None:
    for host_spec, destination in _volume_pairs(service):
        if not destination.startswith(_POSTGRES_DEST):
            continue
        if _is_named_volume(host_spec):
            return PgBind(service_name, None, host_spec, destination)
        host_path = Path(host_spec)
        if not host_path.is_absolute():
            host_path = compose_dir / host_path
        return PgBind(service_name, host_path.resolve(), "", destination)
    return None


def _volume_pairs(service: Mapping[object, object]) -> list[tuple[str, str]]:
    raw = service.get("volumes")
    if not isinstance(raw, list):
        return []
    pairs: list[tuple[str, str]] = []
    for entry in raw:
        if isinstance(entry, str):
            pairs.append(_split_short_volume(entry))
            continue
        if isinstance(entry, dict):
            host = str(entry.get("source") or "")
            dest = str(entry.get("target") or entry.get("destination") or "")
            if host and dest:
                pairs.append((host, dest))
    return pairs


def _split_short_volume(entry: str) -> tuple[str, str]:
    if len(entry) >= 3 and entry[1] == ":":
        rest = entry[2:]
        if ":" not in rest:
            raise PlanError(f"volume is missing a container path: {entry}")
        host_rest, destination = rest.split(":", 1)
        return entry[:2] + host_rest, destination
    if ":" not in entry:
        raise PlanError(f"volume is missing a container path: {entry}")
    host, destination = entry.split(":", 1)
    return host, destination


def _is_named_volume(host_spec: str) -> bool:
    if "/" in host_spec or "\\" in host_spec or host_spec.startswith("."):
        return False
    return not (len(host_spec) >= 3 and host_spec[1] == ":")


def _is_postgres_service(service: str, image: str, mounts: list[Mount]) -> bool:
    if service == "db_postgres":
        return True
    if service != "db":
        return False
    if "postgres" in image:
        return True
    return any(mount.destination.startswith(_POSTGRES_DEST) for mount in mounts)


def _label_compose_file(labels: Mapping[object, object]) -> Path | None:
    raw = str(labels.get("com.docker.compose.project.config_files") or "")
    for part in raw.split(","):
        text = part.strip()
        if text:
            return Path(text)
    return None


def _mount_for_destination(destination: str, mounts: list[Mount]) -> Mount | None:
    for mount in mounts:
        if mount.destination == destination:
            return mount
    return None


def _assert_mount_source(bind: PgBind, mount: Mount) -> None:
    if bind.host_path is not None:
        if mount.mount_type not in {"", "bind"}:
            raise PlanError(f"compose bind {bind.host_path} is mounted as {mount.mount_type}")
        if Path(mount.source).resolve() != bind.host_path.resolve():
            raise PlanError(f"compose data dir {bind.host_path} does not match container mount {mount.source}")
        return
    if mount.mount_type != "volume" or mount.name != bind.volume_name:
        raise PlanError(
            f"compose volume {bind.volume_name} does not match container mount {mount.name or mount.source}"
        )


def _path_inside(path: str, parent: str) -> bool:
    folder = parent.rstrip("/")
    return path == folder or path.startswith(folder + "/")


def _container_id(target: ComposeTarget) -> str:
    text = compose_stdout(target, ["ps", "-q", target.service], _DOCKER_TIMEOUT).strip()
    line = text.splitlines()[0].strip() if text else ""
    if not line:
        raise ComposeError(f"{target.service} has no container")
    return line


def _inspect_one(container_id: str) -> dict[str, object]:
    try:
        payload = json.loads(run_docker(["inspect", container_id], _DOCKER_TIMEOUT))
    except json.JSONDecodeError as exc:
        raise ComposeError("docker inspect was not JSON") from exc
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise ComposeError("docker inspect returned no container")
    return payload[0]


def _identity(target: ComposeTarget) -> tuple[str, str]:
    raw = run_psql(target, _IDENTITY_SQL, _QUERY_TIMEOUT).strip()
    rows = list(csv.reader(io.StringIO(raw)))
    if len(rows) != 1 or len(rows[0]) != 2:
        raise ComposeError("Postgres did not report its data directory")
    return rows[0][0], rows[0][1]
