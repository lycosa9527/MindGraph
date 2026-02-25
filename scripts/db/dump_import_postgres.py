"""
PostgreSQL Dump/Import Script

Standalone script to dump or import PostgreSQL database to/from backup folder.
Runs interactively: prompts for Dump/Import and dry/execute.

Usage:
    python scripts/db/dump_import_postgres.py

Features:
    - Interactive: Dump or Import? (d/i)
    - Prompts for dry run or execute
    - Dump: exports to backup/, creates manifest with table row counts
    - Import: restores from backup/, verifies counts match manifest
    - Self-contained ensure_postgresql_running (check, start if needed)

Requires: psycopg2-binary, PostgreSQL client tools (pg_dump, pg_restore), rich (for progress bar)
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load .env before importing config
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

try:
    import psycopg2
except ImportError:
    psycopg2 = None

from sqlalchemy import inspect, text

from config.database import DATABASE_URL, engine

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

_backup_dir_env = os.getenv("BACKUP_DIR", "backup")
BACKUP_DIR = Path(_backup_dir_env) if Path(_backup_dir_env).is_absolute() else project_root / _backup_dir_env
DUMP_PREFIX = "mindgraph.postgresql"
DUMP_EXT = ".dump"


def _can_connect_postgresql(db_url: str, timeout: int = 2) -> bool:
    """Try to connect to PostgreSQL. Returns True if successful."""
    if psycopg2 is None:
        logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
        return False
    try:
        conn = psycopg2.connect(db_url, connect_timeout=timeout)
        conn.close()
        return True
    except Exception:
        return False


def _try_start_postgresql() -> bool:
    """Attempt to start PostgreSQL. Returns True if start was attempted."""
    if sys.platform == "win32":
        service_names = [
            "postgresql-x64-18", "postgresql-x64-16", "postgresql-x64-15",
            "postgresql-x64-14", "postgresql"
        ]
        for name in service_names:
            try:
                result = subprocess.run(
                    ["net", "start", name],
                    capture_output=True,
                    timeout=10,
                    check=False,
                    text=True
                )
                if result.returncode == 0:
                    logger.info("Started PostgreSQL service: %s", name)
                    return True
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        logger.warning("Could not start PostgreSQL. Try: net start postgresql-x64-XX")
        return False

    try:
        result = subprocess.run(
            ["systemctl", "start", "postgresql"],
            capture_output=True,
            timeout=10,
            check=False
        )
        if result.returncode == 0:
            logger.info("Started PostgreSQL via systemctl")
            return True
        logger.warning("systemctl start postgresql failed. Try: sudo systemctl start postgresql")
        return False
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("systemctl not found. Start PostgreSQL manually.")
        return False


def ensure_postgresql_running(db_url: str) -> bool:
    """
    Ensure PostgreSQL is running. Check connection, try to start if not, retry.

    Returns:
        True if PostgreSQL is reachable, False otherwise.
    """
    if not db_url or "postgresql" not in db_url.lower():
        logger.error("DATABASE_URL must be a PostgreSQL URL")
        return False

    if _can_connect_postgresql(db_url):
        logger.info("PostgreSQL is running")
        return True

    logger.info("PostgreSQL not reachable. Attempting to start...")
    _try_start_postgresql()
    time.sleep(3)

    for attempt in range(3):
        if _can_connect_postgresql(db_url):
            logger.info("PostgreSQL is now running")
            return True
        if attempt < 2:
            time.sleep(2)

    logger.error(
        "PostgreSQL still unreachable. Start manually:\n"
        "  Linux: sudo systemctl start postgresql\n"
        "  Windows: net start postgresql-x64-XX"
    )
    return False


def find_pg_binary(name: str) -> Optional[str]:
    """Find pg_dump or pg_restore binary. Returns path or None."""
    paths = [
        f"/usr/lib/postgresql/18/bin/{name}",
        f"/usr/lib/postgresql/16/bin/{name}",
        f"/usr/lib/postgresql/15/bin/{name}",
        f"/usr/lib/postgresql/14/bin/{name}",
        f"/usr/local/pgsql/bin/{name}",
        f"/usr/bin/{name}",
    ]
    for path in paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path

    try:
        cmd = ["where", name] if sys.platform == "win32" else ["which", name]
        result = subprocess.run(cmd, capture_output=True, timeout=2, check=False)
        if result.returncode == 0 and result.stdout:
            out = result.stdout.decode("utf-8").strip()
            first_line = out.split("\n")[0].strip() if out else ""
            return first_line if first_line else None
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def get_table_row_counts(engine) -> Dict[str, int]:
    """Query row counts for each table. Returns {table: count}."""
    counts: Dict[str, int] = {}
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.connect() as conn:
        for table_name in existing_tables:
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                counts[table_name] = result.scalar() or 0
            except Exception as e:
                logger.debug("Could not count %s: %s", table_name, e)
    return counts


def get_db_stats(engine) -> Tuple[int, int, int, Dict[str, int]]:
    """Get tables, columns, total records. Returns (tables, columns, records, counts)."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    total_columns = 0
    for table_name in existing_tables:
        try:
            columns = inspector.get_columns(table_name)
            total_columns += len(columns)
        except Exception:
            pass

    counts = get_table_row_counts(engine)
    total_records = sum(counts.values())
    return len(existing_tables), total_columns, total_records, counts


def log_db_summary(tables: int, columns: int, records: int) -> None:
    """Log summary of tables, columns, records."""
    logger.info("Database summary: %d tables, %d columns, %d records", tables, columns, records)


class DumpImportProgress:
    """Progress bar for dump/import operations. Uses Rich when available and TTY."""

    def __init__(self, mode: str, total_stages: int, stage_names: Dict[int, str]):
        self.mode = mode
        self.total_stages = total_stages
        self.stage_names = stage_names
        self.use_rich = RICH_AVAILABLE and sys.stdout.isatty()
        self.progress: Any = None
        self.task_id: Any = None
        self.console: Any = None

        if self.use_rich:
            self.console = Console()
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console,
                expand=True
            )

    def __enter__(self) -> "DumpImportProgress":
        if self.use_rich and self.progress:
            self.progress.__enter__()
            self.task_id = self.progress.add_task(
                f"[cyan]{self.mode}: {self.stage_names.get(0, 'Starting')}",
                total=self.total_stages
            )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.use_rich and self.progress:
            self.progress.__exit__(exc_type, exc_val, exc_tb)

    def update(self, stage: int, description: Optional[str] = None) -> None:
        """Update progress to given stage."""
        stage_name = description or self.stage_names.get(stage, f"Stage {stage}")
        if self.use_rich and self.progress and self.task_id is not None:
            self.progress.update(
                self.task_id,
                completed=stage,
                description=f"[cyan]{self.mode}: {stage_name} ({stage}/{self.total_stages})"
            )
        else:
            logger.info("[%s] %s", self.mode, stage_name)


def run_dump(db_url: str, backup_path: Path) -> bool:
    """Run pg_dump. Returns True on success."""
    pg_dump = find_pg_binary("pg_dump")
    if not pg_dump:
        logger.error("pg_dump not found. Install PostgreSQL client tools.")
        return False

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if backup_path.suffix != DUMP_EXT:
        backup_path = backup_path.with_suffix(DUMP_EXT)

    cmd = [
        pg_dump,
        "-Fc",
        "--no-owner",
        "-f",
        str(backup_path),
        db_url
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=3600, check=False, text=True)

    if result.returncode != 0:
        logger.error("pg_dump failed: %s", result.stderr or result.stdout)
        if backup_path.exists():
            backup_path.unlink()
        return False

    if not backup_path.exists() or backup_path.stat().st_size == 0:
        logger.error("Dump file empty or missing")
        return False

    return True


def verify_dump(backup_path: Path) -> bool:
    """Verify dump integrity via pg_restore --list."""
    pg_restore = find_pg_binary("pg_restore")
    if not pg_restore:
        return backup_path.exists() and backup_path.stat().st_size > 0

    result = subprocess.run(
        [pg_restore, "--list", str(backup_path)],
        capture_output=True,
        timeout=60,
        check=False
    )
    return result.returncode == 0


def run_restore(db_url: str, backup_path: Path) -> bool:
    """
    Run pg_restore. Overwrites existing data.

    Uses --clean --if-exists to drop and recreate objects.
    Uses --no-owner to avoid ownership issues when restoring from another machine.
    Uses --single-transaction for atomicity (rollback on failure).
    """
    pg_restore = find_pg_binary("pg_restore")
    if not pg_restore:
        logger.error("pg_restore not found. Install PostgreSQL client tools.")
        return False

    cmd = [
        pg_restore,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--single-transaction",
        "-d",
        db_url,
        str(backup_path)
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=3600, check=False, text=True)

    if result.returncode != 0:
        stderr = result.stderr or ""
        logger.error("pg_restore failed (exit %d): %s", result.returncode, stderr[:1000])
        return False
    return True


def list_dumps() -> List[Path]:
    """List dump files in backup dir, newest first."""
    if not BACKUP_DIR.exists():
        return []
    dumps = [
        p for p in BACKUP_DIR.glob(f"{DUMP_PREFIX}.*{DUMP_EXT}")
        if p.is_file()
    ]
    dumps.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return dumps


def select_dump_file() -> Optional[Path]:
    """Let user select dump file from backup. Returns Path or None."""
    dumps = list_dumps()
    if not dumps:
        logger.error("No dump files found in %s", BACKUP_DIR)
        return None
    if len(dumps) == 1:
        return dumps[0]

    print("\nAvailable dumps:")
    for i, p in enumerate(dumps, 1):
        size_mb = p.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {i}. {p.name} ({size_mb:.2f} MB, {mtime})")
    print(f"  {len(dumps) + 1}. Use latest (default)")

    try:
        choice = input("\nSelect [1]: ").strip() or "1"
        idx = int(choice)
        if 1 <= idx <= len(dumps):
            return dumps[idx - 1]
        return dumps[0]
    except (ValueError, EOFError):
        return dumps[0]


def dump_command(live: bool) -> int:
    """Dump flow. Returns exit code."""
    if "postgresql" not in (DATABASE_URL or "").lower():
        logger.error("DATABASE_URL is not PostgreSQL")
        return 1

    if not ensure_postgresql_running(DATABASE_URL):
        return 1

    tables, columns, total_records, counts = get_db_stats(engine)
    if not counts:
        logger.error("No tables found in database - cannot dump")
        return 1
    log_db_summary(tables, columns, total_records)
    logger.info("Table row counts: %s", counts)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{DUMP_PREFIX}.{timestamp}{DUMP_EXT}"

    if not live:
        logger.info("[DRY RUN] Would dump to %s", backup_path)
        logger.info("[DRY RUN] Would export: %d tables, %d columns, %d records", tables, columns, total_records)
        return 0

    dump_stages = {
        0: "Connecting",
        1: "Getting database stats",
        2: "Running pg_dump",
        3: "Writing manifest",
        4: "Verifying dump",
        5: "Complete"
    }
    with DumpImportProgress("Dump", 5, dump_stages) as prog:
        prog.update(0, "Connected")
        prog.update(1, "Stats collected")
        if not run_dump(DATABASE_URL, backup_path):
            return 1
        prog.update(2, "pg_dump done")

        manifest = {
            "dump_file": backup_path.name,
            "timestamp": datetime.now().isoformat(),
            "source": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "unknown",
            "tables": counts,
            "total_tables": tables,
            "total_columns": columns,
            "total_records": total_records
        }
        manifest_path = backup_path.with_suffix(backup_path.suffix + ".manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        prog.update(3, "Manifest written")

        verified = verify_dump(backup_path)
        prog.update(4, "Verified" if verified else "Verify failed")
        prog.update(5, "Complete")

    if verified:
        logger.info("Dump verified: %s", backup_path.name)
    else:
        logger.warning("Dump verification failed")

    size_mb = backup_path.stat().st_size / (1024 * 1024)
    logger.info("Dump complete: %s (%.2f MB)", backup_path.name, size_mb)
    return 0


def _confirm_overwrite() -> bool:
    """Ask user to confirm overwrite. Returns True to proceed. Full words only."""
    try:
        reply = input(
            "\nWARNING: This will REPLACE all data in the target database. "
            "Stop the application first. Continue? (yes/no): "
        ).strip().lower()
        return reply == "yes"
    except (EOFError, KeyboardInterrupt):
        return False


def import_command(live: bool) -> int:
    """Import flow. Returns exit code."""
    if "postgresql" not in (DATABASE_URL or "").lower():
        logger.error("DATABASE_URL is not PostgreSQL")
        return 1

    dump_path = select_dump_file()
    if not dump_path:
        return 1

    manifest_path = Path(str(dump_path) + ".manifest.json")
    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        return 1

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Manifest corrupted or invalid JSON: %s", e)
        return 1

    expected_counts = manifest.get("tables", {})
    if not expected_counts:
        logger.error("Manifest has no table counts - cannot verify restore")
        return 1

    manifest_tables = manifest.get("total_tables", len(expected_counts))
    manifest_columns = manifest.get("total_columns", 0)
    manifest_records = manifest.get("total_records", sum(expected_counts.values()))

    if not live:
        logger.info("[DRY RUN] Would restore from %s", dump_path.name)
        logger.info("[DRY RUN] Dump contains: %d tables, %d columns, %d records", manifest_tables, manifest_columns, manifest_records)
        logger.info("[DRY RUN] Would REPLACE all existing data")
        if ensure_postgresql_running(DATABASE_URL):
            try:
                current = get_table_row_counts(engine)
            except Exception as e:
                logger.warning("[DRY RUN] Could not check DB state: %s", e)
                current = {}
            refuse = [
                t for t, exp in expected_counts.items()
                if current.get(t, 0) > exp
            ]
            extra_with_data = [
                t for t in set(current.keys()) - set(expected_counts.keys())
                if current.get(t, 0) > 0
            ]
            if refuse or extra_with_data:
                logger.info("[DRY RUN] Would REFUSE: dump older than DB")
                if refuse:
                    logger.info("[DRY RUN]   Tables with more rows in DB: %s", refuse[:5])
                if extra_with_data:
                    logger.info("[DRY RUN]   Extra tables with data: %s", extra_with_data[:5])
            else:
                logger.info("[DRY RUN] Would PROCEED (no data loss)")
        return 0

    if not ensure_postgresql_running(DATABASE_URL):
        return 1

    current_counts = get_table_row_counts(engine)

    manifest_tables = set(expected_counts.keys())
    current_tables = set(current_counts.keys())
    dump_newer_tables = manifest_tables - current_tables
    if dump_newer_tables:
        logger.info(
            "Dump has newer schema: %d table(s) not in DB - restore will create: %s",
            len(dump_newer_tables),
            ", ".join(sorted(dump_newer_tables)[:5])
            + ("..." if len(dump_newer_tables) > 5 else "")
        )

    refuse_reasons: List[str] = []
    for table, expected in expected_counts.items():
        current = current_counts.get(table, 0)
        if current > expected:
            refuse_reasons.append(
                f"  {table}: DB has {current} rows, dump has {expected} - would lose data"
            )

    extra_tables_with_data = [
        t for t in set(current_counts.keys()) - set(expected_counts.keys())
        if current_counts.get(t, 0) > 0
    ]
    if extra_tables_with_data:
        refuse_reasons.append(
            f"  DB has tables not in dump with data (would be dropped): "
            f"{', '.join(sorted(extra_tables_with_data)[:5])}"
            + ("..." if len(extra_tables_with_data) > 5 else "")
        )

    if refuse_reasons:
        logger.error(
            "Refusing import: dump is older than DB, restore would lose data:\n%s",
            "\n".join(refuse_reasons)
        )
        return 1

    if not _confirm_overwrite():
        logger.info("Import cancelled")
        return 0

    import_stages = {
        0: "Checking manifest",
        1: "Checking schema",
        2: "Running pg_restore",
        3: "Resetting sequences",
        4: "Verifying counts",
        5: "Complete"
    }
    with DumpImportProgress("Import", 5, import_stages) as prog:
        prog.update(0, "Manifest loaded")
        prog.update(1, "Schema checked")
        if not run_restore(DATABASE_URL, dump_path):
            return 1
        prog.update(2, "pg_restore done")

        try:
            from utils.migration.sqlite.migration_tables import reset_postgresql_sequences
            reset_postgresql_sequences(engine)
            logger.info("PostgreSQL sequences reset")
        except ImportError as e:
            logger.warning("Could not reset sequences (optional): %s", e)
        except Exception as e:
            logger.warning("Sequence reset had issues: %s", e)
        prog.update(3, "Sequences reset")

        actual_counts = get_table_row_counts(engine)
        prog.update(4, "Verifying counts")
        prog.update(5, "Complete")

    missing_tables: List[str] = []
    count_mismatches: List[Tuple[str, int, int]] = []
    for table, expected in expected_counts.items():
        actual = actual_counts.get(table, -1)
        if actual == -1:
            missing_tables.append(table)
        elif actual != expected:
            count_mismatches.append((table, expected, actual))

    extra_tables = set(actual_counts.keys()) - set(expected_counts.keys())
    if extra_tables:
        logger.warning(
            "DB has %d extra table(s) not in manifest: %s",
            len(extra_tables),
            ", ".join(sorted(extra_tables)[:10]) + ("..." if len(extra_tables) > 10 else "")
        )

    if missing_tables:
        logger.error("Tables missing after restore: %s", ", ".join(sorted(missing_tables)))
        return 1

    if count_mismatches:
        logger.error("Row count mismatch after restore:")
        for table, exp, act in count_mismatches:
            logger.error("  %s: expected %d, got %d", table, exp, act)
        return 1

    tables, columns, total_records, _ = get_db_stats(engine)
    log_db_summary(tables, columns, total_records)
    logger.info("Import complete. All table counts match manifest.")
    return 0


def prompt_dump_or_import() -> Optional[str]:
    """Ask user: dump or import. Returns 'd' or 'i' or None to exit. Full words only."""
    while True:
        try:
            choice = input("\nDump or Import? (dump/import/quit): ").strip().lower()
            if choice == "quit":
                return None
            if choice == "dump":
                return "d"
            if choice == "import":
                return "i"
        except (EOFError, KeyboardInterrupt):
            return None
        print("Enter 'dump', 'import', or 'quit' (full words only).")


def prompt_dry_run_or_execute() -> bool:
    """Ask user: dry run or execute. Returns True for execute, False for dry run. Full words only."""
    while True:
        try:
            choice = input("Dry run or Execute? (dry/execute) [dry]: ").strip().lower() or "dry"
            if choice == "dry":
                return False
            if choice == "execute":
                return True
        except (EOFError, KeyboardInterrupt):
            return False
        print("Enter 'dry' or 'execute' (full words only).")


def main() -> int:
    """Main entry point."""
    choice = prompt_dump_or_import()
    if not choice:
        logger.info("Exiting")
        return 0

    live = prompt_dry_run_or_execute()
    if live:
        logger.info("Execute mode - operations will run")
    else:
        logger.info("Dry run mode - no changes will be made")

    if choice == "d":
        return dump_command(live)
    return import_command(live)


if __name__ == "__main__":
    sys.exit(main())
