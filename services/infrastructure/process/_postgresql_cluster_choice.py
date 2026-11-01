"""
Choose the local PostgreSQL data directory for connect-only startup.

Records the choice in ``POSTGRESQL_DATA_DIR`` so the next launch uses the
cluster that holds the MindGraph database.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from services.infrastructure.process._postgresql_discovery import (
    RankedCluster,
    clusters_on_port,
    discover_ranked_cluster_details,
)
from services.infrastructure.process._postgresql_paths import is_initialized_cluster, read_cluster_port
from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig

logger = logging.getLogger(__name__)

_ENV_KEY = "POSTGRESQL_DATA_DIR"


@dataclass(frozen=True)
class ClusterChoice:
    """Selected data directory and the clusters surveyed on the target port."""

    path: Path | None
    on_port: tuple[RankedCluster, ...]
    other_port: RankedCluster | None = None


def _paths_match(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return os.path.normpath(str(left)) == os.path.normpath(str(right))


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def env_file_path() -> Path:
    """``.env`` path, or ``MINDGRAPH_ENV_FILE`` when set."""
    override = os.getenv("MINDGRAPH_ENV_FILE", "").strip()
    if override:
        return Path(override).expanduser()
    return _project_root() / ".env"


def _assignment_in_file(env_path: Path, key: str) -> str:
    """Return the value of ``key`` in ``env_path``, or an empty string."""
    if not env_path.is_file():
        return ""
    try:
        raw = env_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    prefix = f"{key}="
    for raw_line in raw.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        return stripped[len(prefix) :].strip().strip("'").strip('"')
    return ""


def configured_data_dir(port: int) -> Path | None:
    """Return ``POSTGRESQL_DATA_DIR`` from the environment or ``.env`` when it is on ``port``."""
    raw = os.getenv(_ENV_KEY, "").strip() or _assignment_in_file(env_file_path(), _ENV_KEY)
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not is_initialized_cluster(path):
        return None
    if read_cluster_port(path) != port:
        return None
    return path


def env_locks_data_dir(data_path: Path, port: int) -> bool:
    """True when ``.env`` already names this data directory and it is not a distro ``main``."""
    configured = configured_data_dir(port)
    if configured is None or not _paths_match(configured, data_path):
        return False
    return not _is_distro_main(configured)


def _named_mindgraph(on_port: list[RankedCluster]) -> RankedCluster | None:
    named = [item for item in on_port if "mindgraph" in str(item.path).lower()]
    if not named:
        return None
    return max(named, key=lambda item: item.score)


def choose_cluster(config: PostgresRuntimeConfig) -> ClusterChoice:
    """
    Pick the local cluster launch should use.

    After the survey, ``POSTGRESQL_DATA_DIR`` in ``.env`` locks that cluster when
    it is one of the directories that already contains the database. A distro
    ``main`` path does not lock. A directory whose path contains ``mindgraph``
    is next. An empty ``<version>/main`` directory is not kept just because it
    is the configured path.
    """
    if sys.platform == "win32" or not config.is_local:
        return ClusterChoice(path=None, on_port=())

    ranked = discover_ranked_cluster_details(config)
    on_port = clusters_on_port(ranked, config.port)
    verified = [item for item in on_port if item.has_database]
    configured = configured_data_dir(config.port)
    other = next((item for item in ranked if item.has_database and item.port != config.port), None)
    locked = _env_listed_cluster(configured, verified)
    if locked is not None:
        return ClusterChoice(path=locked, on_port=tuple(on_port), other_port=other)
    selected = _select_on_port(configured, verified, on_port)
    return ClusterChoice(path=selected, on_port=tuple(on_port), other_port=other)


def _env_listed_cluster(configured: Path | None, verified: list[RankedCluster]) -> Path | None:
    """Lock ``.env`` when that surveyed cluster already contains the database."""
    if configured is None or _is_distro_main(configured):
        return None
    for item in verified:
        if _paths_match(item.path, configured):
            return item.path
    return None


def _select_on_port(
    configured: Path | None,
    verified: list[RankedCluster],
    on_port: list[RankedCluster],
) -> Path | None:
    """Prefer a cluster that has the database over an empty upgrade ``main``."""
    if verified:
        best = max(verified, key=lambda item: (item.score, _cluster_size_hint(item.path)))
        return best.path
    named = _named_mindgraph(on_port)
    if named is not None:
        return named.path
    if configured is None:
        return None
    if _is_distro_main(configured):
        others = [item for item in on_port if not _paths_match(item.path, configured)]
        if others:
            return None
    return configured


def _is_distro_main(data_path: Path) -> bool:
    return data_path.name.lower() == "main" and data_path.parent.name.isdigit()


def _cluster_size_hint(data_path: Path) -> int:
    base_dir = data_path / "base"
    if not base_dir.is_dir():
        return 0
    try:
        return sum(1 for entry in base_dir.iterdir() if entry.is_dir())
    except OSError:
        return 0


def _replace_env_key(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    updated: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(prefix):
            updated.append(f"{key}={value}\n")
            replaced = True
            continue
        if line.endswith("\n"):
            updated.append(line)
        else:
            updated.append(f"{line}\n")
    if not replaced:
        if updated and not updated[-1].endswith("\n"):
            updated[-1] = f"{updated[-1]}\n"
        updated.append(f"{key}={value}\n")
    return updated


def _env_has_same_dir(env_path: Path, data_path: Path) -> bool:
    current = _assignment_in_file(env_path, _ENV_KEY)
    if not current:
        return False
    return _paths_match(Path(current).expanduser(), data_path)


def publish_cluster_env(data_path: Path) -> str:
    """
    Write ``POSTGRESQL_DATA_DIR`` and return ``updated``, ``unchanged``, or ``missing``.

    ``missing`` means the env file could not be updated. The process environment
    is set either way.
    """
    value = str(data_path)
    os.environ[_ENV_KEY] = value
    env_path = env_file_path()
    if _env_has_same_dir(env_path, data_path):
        return "unchanged"
    if not env_path.is_file():
        return "missing"
    try:
        raw = env_path.read_text(encoding="utf-8")
        lines = raw.splitlines(keepends=True)
        if not lines:
            lines = ["\n"]
        env_path.write_text("".join(_replace_env_key(lines, _ENV_KEY, value)), encoding="utf-8")
    except OSError as exc:
        logger.debug("Could not write %s: %s", env_path, exc)
        return "missing"
    return "updated"


def _database_label(item: RankedCluster, database: str) -> str:
    if item.has_database:
        return f"database {database}"
    return "database not found"


def announce_cluster_choice(config: PostgresRuntimeConfig, choice: ClusterChoice, env_status: str) -> None:
    """Print the surveyed clusters and the ``.env`` line launch is using."""
    try:
        if choice.on_port:
            print(f"[POSTGRESQL] Clusters on port {config.port}:")
            for item in choice.on_port:
                print(f"[POSTGRESQL]   {item.path} — {_database_label(item, config.database)}")
        if choice.path is None:
            if choice.other_port is not None:
                print(
                    f"[POSTGRESQL] Database {config.database} is in {choice.other_port.path} "
                    f"(port {choice.other_port.port})."
                )
                print(
                    f"[POSTGRESQL] Set POSTGRESQL_DATA_DIR={choice.other_port.path} "
                    f"and POSTGRESQL_PORT={choice.other_port.port} in .env, "
                    "and use that port in DATABASE_URL."
                )
                return
            print(f"[POSTGRESQL] No cluster on port {config.port} contains database {config.database}.")
            print("[POSTGRESQL] Set POSTGRESQL_DATA_DIR in .env to that data directory, then restart.")
            return
        print(f"[POSTGRESQL] Using cluster {choice.path}")
        if env_status == "updated":
            print(f"[POSTGRESQL] Set POSTGRESQL_DATA_DIR={choice.path} in .env")
        elif env_status == "unchanged":
            print(f"[POSTGRESQL] .env already has POSTGRESQL_DATA_DIR={choice.path}")
        else:
            print(f"[POSTGRESQL] Add this to .env: POSTGRESQL_DATA_DIR={choice.path}")
    except (ValueError, OSError):
        pass
