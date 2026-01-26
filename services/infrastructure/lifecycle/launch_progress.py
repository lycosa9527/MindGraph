"""
Application Launch Progress Tracker

Provides real-time progress bar using Rich library for application startup.
Shows initialization stages during FastAPI application lifespan startup.

Author: MindSpring Team
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

# Application launch stages
STAGE_SIGNAL_HANDLERS = 0
STAGE_REDIS = 1
STAGE_QDRANT = 2
STAGE_CELERY = 3
STAGE_DEPENDENCIES = 4
STAGE_DB_INTEGRITY = 5
STAGE_DB_INIT = 6
STAGE_CACHE_LOADING = 7
STAGE_IP_DATABASE = 8
STAGE_IP_WHITELIST = 9
STAGE_LLM_SERVICE = 10
STAGE_PLAYWRIGHT = 11
STAGE_CLEANUP_SCHEDULER = 12
STAGE_BACKUP_SCHEDULER = 13
STAGE_PROCESS_MONITOR = 14
STAGE_HEALTH_MONITOR = 15
STAGE_DIAGRAM_CACHE = 16
STAGE_SMS_NOTIFICATION = 17
STAGE_COMPLETE = 18

STAGE_NAMES = {
    STAGE_SIGNAL_HANDLERS: "Registering Signal Handlers",
    STAGE_REDIS: "Initializing Redis",
    STAGE_QDRANT: "Initializing Qdrant",
    STAGE_CELERY: "Checking Celery Worker",
    STAGE_DEPENDENCIES: "Checking System Dependencies",
    STAGE_DB_INTEGRITY: "Checking Database Integrity",
    STAGE_DB_INIT: "Initializing Database",
    STAGE_CACHE_LOADING: "Loading User Cache",
    STAGE_IP_DATABASE: "Loading IP Geolocation Database",
    STAGE_IP_WHITELIST: "Loading IP Whitelist",
    STAGE_LLM_SERVICE: "Initializing LLM Service",
    STAGE_PLAYWRIGHT: "Verifying Playwright",
    STAGE_CLEANUP_SCHEDULER: "Starting Cleanup Scheduler",
    STAGE_BACKUP_SCHEDULER: "Starting Backup Scheduler",
    STAGE_PROCESS_MONITOR: "Starting Process Monitor",
    STAGE_HEALTH_MONITOR: "Starting Health Monitor",
    STAGE_DIAGRAM_CACHE: "Initializing Diagram Cache",
    STAGE_SMS_NOTIFICATION: "Sending Startup Notification",
    STAGE_COMPLETE: "Complete"
}

TOTAL_STAGES = len(STAGE_NAMES) - 1  # Exclude COMPLETE stage


class ApplicationLaunchProgressTracker:
    """
    Tracks and displays application launch progress using Rich progress bars.
    
    Automatically detects if running in TTY (interactive terminal) and falls back
    to logging if not available (e.g., server startup logs).
    
    Only displays progress for main worker to avoid duplicate output in multi-worker setups.
    """

    def __init__(self, is_main_worker: bool = True):
        """
        Initialize progress tracker.
        
        Args:
            is_main_worker: Whether this is the main worker (only main worker shows progress)
        """
        self.is_main_worker = is_main_worker
        self.current_stage = STAGE_SIGNAL_HANDLERS
        self.errors = []
        
        # Only show progress for main worker
        # Check if we can use Rich (TTY available and Rich installed)
        self.use_rich = (
            is_main_worker and 
            RICH_AVAILABLE and 
            sys.stdout.isatty()
        )
        
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
                expand=True,
                refresh_per_second=10
            )
            self.stage_task = None
        else:
            self.console = None
            self.progress = None
            self.stage_task = None

    def __enter__(self):
        """Context manager entry."""
        if self.use_rich:
            self.progress.__enter__()
            # Create single main stage progress task (only one bar)
            self.stage_task = self.progress.add_task(
                f"[cyan]{STAGE_NAMES[STAGE_SIGNAL_HANDLERS]}",
                total=TOTAL_STAGES
            )
        elif self.is_main_worker:
            logger.info("[Launch] Starting application initialization...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.use_rich and self.progress:
            self.progress.__exit__(exc_type, exc_val, exc_tb)

    def update_stage(self, stage: int, description: Optional[str] = None) -> None:
        """
        Update current launch stage.
        
        Args:
            stage: Stage number (use STAGE_* constants)
            description: Optional custom description
        """
        self.current_stage = stage
        stage_name = description or STAGE_NAMES.get(stage, f"Stage {stage}")
        
        if self.use_rich and self.stage_task is not None:
            # Update the single progress bar in place (Rich automatically refreshes)
            self.progress.update(
                self.stage_task,
                completed=stage,
                description=f"[cyan]{stage_name}"
            )
        elif self.is_main_worker:
            logger.info("[Launch] %s", stage_name)

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
        elif self.is_main_worker:
            logger.warning("[Launch] Error: %s", error_message)

    def print_summary(self) -> None:
        """
        Print final launch summary.
        """
        if self.use_rich and self.console:
            self.console.print("\n[bold green]Application Launch Summary[/bold green]")
            self.console.print(f"  Stages completed: {self.current_stage}/{TOTAL_STAGES}")
            
            if self.errors:
                self.console.print(f"\n[bold yellow]Warnings ({len(self.errors)}):[/bold yellow]")
                for error in self.errors[:10]:
                    self.console.print(f"  - {error}")
                if len(self.errors) > 10:
                    self.console.print(f"  ... and {len(self.errors) - 10} more")
        elif self.is_main_worker:
            logger.info("=" * 80)
            logger.info("Application Launch Summary")
            logger.info("=" * 80)
            logger.info("Stages completed: %d/%d", self.current_stage, TOTAL_STAGES)
            
            if self.errors:
                logger.warning("Warnings (%d):", len(self.errors))
                for error in self.errors[:10]:
                    logger.warning("  - %s", error)
                if len(self.errors) > 10:
                    logger.warning("  ... and %d more", len(self.errors) - 10)
