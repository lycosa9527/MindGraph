"""
SQLite Migration Progress Tracker

Provides real-time progress bar using Rich library for SQLite to PostgreSQL migration.
Shows migration stages, per-table progress, and record counts.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import sys
import logging
from typing import Optional

try:
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Migration stages
STAGE_PREREQUISITES = 0
STAGE_LOCK = 1
STAGE_BACKUP = 2
STAGE_CONNECT = 3
STAGE_CREATE_TABLES = 4
STAGE_MIGRATE_TABLES = 5
STAGE_RESET_SEQUENCES = 6
STAGE_VERIFY = 7
STAGE_MOVE_SQLITE = 8
STAGE_CREATE_MARKER = 9
STAGE_COMPLETE = 10

STAGE_NAMES = {
    STAGE_PREREQUISITES: "Checking Prerequisites",
    STAGE_LOCK: "Acquiring Lock",
    STAGE_BACKUP: "Backing Up SQLite",
    STAGE_CONNECT: "Connecting Databases",
    STAGE_CREATE_TABLES: "Creating PostgreSQL Tables",
    STAGE_MIGRATE_TABLES: "Migrating Tables",
    STAGE_RESET_SEQUENCES: "Resetting Sequences",
    STAGE_VERIFY: "Verifying Migration",
    STAGE_MOVE_SQLITE: "Moving SQLite to Backup",
    STAGE_CREATE_MARKER: "Creating Migration Marker",
    STAGE_COMPLETE: "Complete"
}

TOTAL_STAGES = len(STAGE_NAMES) - 1  # Exclude COMPLETE stage


class MigrationProgressTracker:
    """
    Tracks and displays migration progress using Rich progress bars.

    Automatically detects if running in TTY (interactive terminal) and falls back
    to logging if not available (e.g., server startup logs).
    """

    def __init__(self, total_tables: int = 0):
        """
        Initialize progress tracker.

        Args:
            total_tables: Total number of tables to migrate
        """
        self.total_tables = total_tables
        self.current_stage = STAGE_PREREQUISITES
        self.current_table = None
        self.current_table_index = 0
        self.current_table_records = 0
        self.current_table_total = 0
        self.tables_completed = 0
        self.total_records = 0
        self.errors = []

        # Check if we can use Rich (TTY available and Rich installed)
        self.use_rich = RICH_AVAILABLE and sys.stdout.isatty()

        if self.use_rich:
            self.console = Console()
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=self.console,
                expand=True
            )
            self.stage_task = None
            self.table_task = None
            self.record_task = None
        else:
            self.console = None
            self.progress = None
            self.stage_task = None
            self.table_task = None
            self.record_task = None

    def __enter__(self):
        """Context manager entry."""
        if self.use_rich and self.progress is not None:
            self.progress.__enter__()
            # Create main stage progress task
            self.stage_task = self.progress.add_task(
                f"[cyan]Stage: {STAGE_NAMES[STAGE_PREREQUISITES]}",
                total=TOTAL_STAGES
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.use_rich and self.progress:
            self.progress.__exit__(exc_type, exc_val, exc_tb)

    def update_stage(self, stage: int, description: Optional[str] = None) -> None:
        """
        Update current migration stage.

        Args:
            stage: Stage number (use STAGE_* constants)
            description: Optional custom description
        """
        self.current_stage = stage
        stage_name = description or STAGE_NAMES.get(stage, f"Stage {stage}")

        if self.use_rich and self.progress is not None and self.stage_task is not None:
            self.progress.update(
                self.stage_task,
                completed=stage,
                description=f"[cyan]Stage: {stage_name} ({stage}/{TOTAL_STAGES})"
            )
        else:
            logger.info("[Migration] %s", stage_name)

    def start_table_migration(self, table_name: str, table_index: int, total_records: int) -> None:
        """
        Start migrating a table.

        Args:
            table_name: Name of the table
            table_index: Current table index (1-based)
            total_records: Total number of records in the table
        """
        self.current_table = table_name
        self.current_table_index = table_index
        self.current_table_total = total_records
        self.current_table_records = 0

        if self.use_rich and self.progress is not None:
            # Create table task if it doesn't exist
            if self.table_task is None:
                self.table_task = self.progress.add_task(
                    f"[green]Table: {table_name} ({table_index}/{self.total_tables})",
                    total=self.total_tables
                )
            else:
                self.progress.update(
                    self.table_task,
                    completed=table_index - 1,
                    description=f"[green]Table: {table_name} ({table_index}/{self.total_tables})"
                )

            # Create record task for this table if it has records
            if total_records > 0:
                if self.record_task is None:
                    self.record_task = self.progress.add_task(
                        f"[yellow]Records: {table_name}",
                        total=total_records
                    )
                else:
                    self.progress.reset(
                        self.record_task,
                        total=total_records,
                        description=f"[yellow]Records: {table_name}"
                    )
        else:
            logger.info(
                "[Migration] Migrating table %d/%d: %s (%d records)",
                table_index, self.total_tables, table_name, total_records
            )

    def update_table_records(self, records_migrated: int) -> None:
        """
        Update number of records migrated for current table.

        Args:
            records_migrated: Number of records migrated so far
        """
        self.current_table_records = records_migrated

        if self.use_rich and self.progress is not None and self.record_task is not None:
            self.progress.update(self.record_task, completed=records_migrated)
        elif self.current_table_total > 10000:  # Only log for large tables
            progress_pct = (records_migrated / self.current_table_total) * 100
            logger.debug(
                "[Migration] %s: %d/%d records (%.1f%%)",
                self.current_table, records_migrated, self.current_table_total, progress_pct
            )

    def complete_table(self, records_migrated: int) -> None:
        """
        Mark current table as completed.

        Args:
            records_migrated: Total number of records migrated
        """
        self.tables_completed += 1
        self.total_records += records_migrated

        if self.use_rich and self.progress is not None and self.table_task is not None:
            self.progress.update(self.table_task, completed=self.tables_completed)
            if self.record_task is not None:
                self.progress.update(self.record_task, completed=self.current_table_total)
        else:
            logger.info(
                "[Migration] ✓ Completed table %d/%d: %s (%d records)",
                self.current_table_index, self.total_tables, self.current_table, records_migrated
            )

    def add_error(self, error_message: str) -> None:
        """
        Add an error message.

        Args:
            error_message: Error message to add
        """
        self.errors.append(error_message)
        if self.use_rich:
            # Errors are shown in final summary, not in progress bar
            pass
        else:
            logger.warning("[Migration] Error: %s", error_message)

    def print_summary(self, stats: Optional[dict] = None) -> None:
        """
        Print final migration summary.

        Args:
            stats: Optional statistics dictionary
        """
        if self.use_rich and self.console:
            self.console.print("\n[bold green]Migration Summary[/bold green]")
            self.console.print(f"  Tables migrated: {self.tables_completed}/{self.total_tables}")
            self.console.print(f"  Total records: {self.total_records:,}")

            if self.errors:
                self.console.print(f"\n[bold yellow]Warnings ({len(self.errors)}):[/bold yellow]")
                for error in self.errors[:10]:
                    self.console.print(f"  - {error}")
                if len(self.errors) > 10:
                    self.console.print(f"  ... and {len(self.errors) - 10} more")

            if stats:
                verification = stats.get('verification', {})
                if verification:
                    mismatches = verification.get('mismatches', [])
                    if mismatches:
                        self.console.print(f"\n[bold yellow]Verification Mismatches: {len(mismatches)}[/bold yellow]")
        else:
            logger.info("=" * 80)
            logger.info("Migration Summary")
            logger.info("=" * 80)
            logger.info("Tables migrated: %d/%d", self.tables_completed, self.total_tables)
            logger.info("Total records: %d", self.total_records)

            if self.errors:
                logger.warning("Warnings (%d):", len(self.errors))
                for error in self.errors[:10]:
                    logger.warning("  - %s", error)
                if len(self.errors) > 10:
                    logger.warning("  ... and %d more", len(self.errors) - 10)

            if stats:
                verification = stats.get('verification', {})
                if verification:
                    mismatches = verification.get('mismatches', [])
                    if mismatches:
                        logger.warning("Verification Mismatches: %d", len(mismatches))
