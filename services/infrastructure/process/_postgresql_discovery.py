"""
Discover local PostgreSQL data directories that host the MindGraph database.

Scans known filesystem roots, verifies ``PG_VERSION``, ranks clusters by port and
whether the configured database name exists, then returns best-first candidates
for connect-only startup after apt upgrades or broken ``pg_lsclusters`` entries.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import psycopg

from services.infrastructure.process._postgresql_helpers import (
    cleanup_stale_pid_file,
    cluster_postmaster_pid,
    launch_command_as_postgres,
    postgresql_accepts_connections,
)
from services.infrastructure.process._postgresql_paths import (
    find_postgres_binaries,
    find_system_postgresql_cluster,
    is_initialized_cluster,
    linux_native_cluster_dir,
    read_cluster_port,
    ubuntu_persistent_cluster_dir,
)
from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig
from services.utils.error_types import PG_CONNECT_ERRORS

logger = logging.getLogger(__name__)

_MAX_SCANNED_CLUSTERS = 32
_MAX_OFFLINE_DB_CHECKS = 8
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class RankedCluster:
    """Scored PostgreSQL data directory candidate."""

    path: Path
    port: int
    score: int
    has_database: bool


def _safe_sql_identifier(name: str, fallback: str = "mindgraph") -> str:
    if _SAFE_IDENTIFIER.fullmatch(name):
        return name
    return fallback


def _cluster_base_oid_count(data_path: Path) -> int:
    base_dir = data_path / "base"
    if not base_dir.is_dir():
        return 0
    try:
        return sum(1 for entry in base_dir.iterdir() if entry.is_dir())
    except OSError:
        return 0


def _scan_root_for_clusters(root: Path, limit: int) -> list[Path]:
    """Return initialized cluster paths under ``root`` (shallow sweep)."""
    found: list[Path] = []
    seen: set[str] = set()

    def append(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        key = str(resolved)
        if key in seen:
            return
        if not is_initialized_cluster(resolved):
            return
        seen.add(key)
        found.append(resolved)

    append(root)
    if len(found) >= limit or not root.is_dir():
        return found[:limit]

    try:
        for child in root.iterdir():
            append(child)
            if len(found) >= limit:
                break
            if child.is_dir():
                for nested in child.iterdir():
                    append(nested)
                    if len(found) >= limit:
                        break
    except OSError as exc:
        logger.debug("Cluster scan failed under %s: %s", root, exc)

    return found[:limit]


def _filesystem_scan_roots() -> list[Path]:
    """Build ordered roots to scan for PostgreSQL data directories."""
    roots: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        try:
            resolved = path.expanduser()
        except OSError:
            return
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        roots.append(resolved)

    data_dir = os.getenv("POSTGRESQL_DATA_DIR", "").strip()
    if data_dir:
        configured = Path(data_dir)
        add(configured)
        add(configured.parent)

    add(Path("/var/lib/postgresql"))
    add(linux_native_cluster_dir())
    add(linux_native_cluster_dir().parent)
    add(ubuntu_persistent_cluster_dir())
    add(Path("storage/postgresql"))
    add(Path("storage"))

    project_root = os.getenv("MINDGRAPH_PROJECT_ROOT", "").strip()
    if project_root:
        add(Path(project_root) / "storage" / "postgresql")
        add(Path(project_root) / "storage")

    registered = find_system_postgresql_cluster()
    if registered is not None:
        add(registered[0])

    return roots


def scan_local_cluster_dirs(limit: int = _MAX_SCANNED_CLUSTERS) -> list[Path]:
    """Sweep known paths and return unique initialized PostgreSQL data directories."""
    clusters: list[Path] = []
    seen: set[str] = set()

    for root in _filesystem_scan_roots():
        remaining = limit - len(clusters)
        if remaining <= 0:
            break
        for candidate in _scan_root_for_clusters(root, remaining):
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            clusters.append(candidate)

    return clusters


def _database_exists_on_running_server(host: str, port: int, database: str) -> bool:
    probe_url = f"postgresql://postgres@{host}:{port}/postgres"
    query = "SELECT 1 FROM pg_database WHERE datname = %s"
    try:
        with psycopg.connect(probe_url, connect_timeout=2) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (database,))
                return cursor.fetchone() is not None
    except (*PG_CONNECT_ERRORS,):
        return False


def _offline_cluster_has_database(data_path: Path, database: str) -> bool:
    """Probe a stopped cluster in single-user mode (read-only catalog lookup)."""
    postgres_binary, _initdb = find_postgres_binaries()
    if postgres_binary is None:
        return False

    cleanup_stale_pid_file(data_path)
    if cluster_postmaster_pid(data_path) is not None:
        port = read_cluster_port(data_path)
        safe_name = _safe_sql_identifier(database)
        return _database_exists_on_running_server("127.0.0.1", port, safe_name)

    safe_name = _safe_sql_identifier(database)
    sql = f"SELECT 1 FROM pg_database WHERE datname = '{safe_name}';\n"
    cmd = launch_command_as_postgres(
        [postgres_binary, "--single", "-D", str(data_path), "-F", "postgres"],
    )
    try:
        result = subprocess.run(
            cmd,
            input=sql,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError, ValueError) as exc:
        logger.debug("Offline database probe failed for %s: %s", data_path, exc)
        return False

    if result.returncode != 0:
        logger.debug(
            "Offline database probe for %s returned rc=%s: %s",
            data_path,
            result.returncode,
            result.stderr.strip(),
        )
        return False

    output = result.stdout
    return "(1 row)" in output or "\n1\n" in output


def cluster_has_database(data_path: Path, database: str, port: int) -> bool:
    """Return True when ``database`` exists in the cluster at ``data_path``."""
    cluster_port = read_cluster_port(data_path)
    if cluster_port != port:
        return False

    safe_name = _safe_sql_identifier(database)
    host = "127.0.0.1"
    running_pid = cluster_postmaster_pid(data_path)
    if running_pid is not None:
        return _database_exists_on_running_server(host, port, safe_name)

    if postgresql_accepts_connections(host, port):
        return False

    return _offline_cluster_has_database(data_path, safe_name)


def _score_cluster(data_path: Path, database: str, target_port: int, has_database: bool) -> RankedCluster:
    port = read_cluster_port(data_path)
    score = 0
    path_text = str(data_path).lower()
    db_lower = database.lower()

    if has_database:
        score += 1000
    if port == target_port:
        score += 200
    if db_lower in path_text:
        score += 80
    if "mindgraph" in path_text:
        score += 60
    if data_path.name.lower() in (db_lower, "mindgraph", "main"):
        score += 40

    score += min(_cluster_base_oid_count(data_path), 25)
    return RankedCluster(path=data_path, port=port, score=score, has_database=has_database)


def discover_ranked_cluster_details(
    config: PostgresRuntimeConfig,
    *,
    verify_database: bool = True,
) -> list[RankedCluster]:
    """
    Scan local paths, locate clusters that contain ``config.database``, rank best-first.

    Clusters on ``config.port`` with a verified MindGraph database are preferred.
    Set ``verify_database=False`` for a fast filesystem-only sweep (dependency checks).
    """
    database = _safe_sql_identifier(config.database)
    target_port = config.port
    candidates = scan_local_cluster_dirs()

    ranked: list[RankedCluster] = []
    offline_checks = 0

    port_matches = [path for path in candidates if read_cluster_port(path) == target_port]
    other_ports = [path for path in candidates if read_cluster_port(path) != target_port]

    for data_path in port_matches:
        has_database = False
        if verify_database and offline_checks < _MAX_OFFLINE_DB_CHECKS:
            has_database = cluster_has_database(data_path, database, target_port)
            offline_checks += 1
        ranked.append(_score_cluster(data_path, database, target_port, has_database))

    for data_path in other_ports:
        ranked.append(_score_cluster(data_path, database, target_port, False))

    ranked.sort(key=lambda item: item.score, reverse=True)

    if ranked:
        best = ranked[0]
        logger.info(
            "Discovered %d local PostgreSQL cluster candidate(s); best=%s port=%s database=%s",
            len(ranked),
            best.path,
            best.port,
            "found" if best.has_database else "unverified",
        )
        try:
            print(
                "[POSTGRESQL] Discovered local cluster candidates "
                f"({len(ranked)} found, best: {best.path}, port {best.port}, "
                f"database {'found' if best.has_database else 'unverified'})"
            )
        except (ValueError, OSError):
            pass
    else:
        logger.info("No local PostgreSQL cluster directories discovered")

    return ranked


def discover_ranked_clusters(
    config: PostgresRuntimeConfig,
    *,
    verify_database: bool = True,
) -> list[Path]:
    """Return ranked cluster data paths (best MindGraph match first)."""
    return [item.path for item in discover_ranked_cluster_details(config, verify_database=verify_database)]


def clusters_on_port(ranked: list[RankedCluster], port: int) -> list[RankedCluster]:
    """Filter ranked clusters configured to listen on ``port``."""
    return [item for item in ranked if item.port == port]


def discover_persistent_cluster_dirs(
    database: str = "mindgraph",
    port: int = 5432,
) -> list[Path]:
    """Backward-compatible wrapper returning ranked cluster paths."""
    config = PostgresRuntimeConfig(
        database_url=f"postgresql://mindgraph_app:@localhost:{port}/{database}",
        host="localhost",
        port=port,
        port_str=str(port),
        database=database,
        runtime_user="mindgraph_app",
        provision_user="mindgraph_user",
        provision_password="",
        spawn_subprocess=False,
        is_local=True,
    )
    return discover_ranked_clusters(config)
