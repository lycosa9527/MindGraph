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
import time
import logging
import threading
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType

try:
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
    from rich.console import Console
    from rich.rule import Rule
    from rich.panel import Panel
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
STAGE_DB_CONNECTION = 6
STAGE_DB_TABLES = 7
STAGE_DB_MIGRATIONS = 8
STAGE_CACHE_LOADING = 9
STAGE_IP_DATABASE = 10
STAGE_IP_WHITELIST = 11
STAGE_LLM_CLIENTS = 12
STAGE_LLM_PROMPTS = 13
STAGE_LLM_RATE_LIMITERS = 14
STAGE_LLM_LOAD_BALANCER = 15
STAGE_PLAYWRIGHT = 16
STAGE_CLEANUP_SCHEDULER = 17
STAGE_BACKUP_SCHEDULER = 18
STAGE_PROCESS_MONITOR = 19
STAGE_HEALTH_MONITOR = 20
STAGE_DIAGRAM_CACHE = 21
STAGE_SMS_NOTIFICATION = 22
STAGE_COMPLETE = 23

STAGE_NAMES = {
    STAGE_SIGNAL_HANDLERS: "Registering Signal Handlers",
    STAGE_REDIS: "Initializing Redis Database",
    STAGE_QDRANT: "Initializing Qdrant Vector Database",
    STAGE_CELERY: "Checking Celery Worker",
    STAGE_DEPENDENCIES: "Checking System Dependencies",
    STAGE_DB_INTEGRITY: "Checking PostgreSQL Database Integrity",
    STAGE_DB_CONNECTION: "Connecting to PostgreSQL Database",
    STAGE_DB_TABLES: "Verifying PostgreSQL Tables",
    STAGE_DB_MIGRATIONS: "Running Database Migrations",
    STAGE_CACHE_LOADING: "Loading User Cache",
    STAGE_IP_DATABASE: "Loading IP Geolocation Database",
    STAGE_IP_WHITELIST: "Loading IP Whitelist",
    STAGE_LLM_CLIENTS: "Initializing LLM Clients",
    STAGE_LLM_PROMPTS: "Loading LLM Prompts",
    STAGE_LLM_RATE_LIMITERS: "Configuring LLM Rate Limiters",
    STAGE_LLM_LOAD_BALANCER: "Initializing LLM Load Balancer",
    STAGE_PLAYWRIGHT: "Verifying Playwright",
    STAGE_CLEANUP_SCHEDULER: "Starting Cleanup Scheduler",
    STAGE_BACKUP_SCHEDULER: "Starting Backup Scheduler",
    STAGE_PROCESS_MONITOR: "Starting Process Monitor",
    STAGE_HEALTH_MONITOR: "Starting Health Monitor",
    STAGE_DIAGRAM_CACHE: "Initializing Diagram Cache",
    STAGE_SMS_NOTIFICATION: "Sending Startup Notification",
    STAGE_COMPLETE: "Complete"
}

# Total number of initialization stages (excluding COMPLETE marker)
# Stages 0-22 are actual initialization stages (23 stages total)
# Stage 23 (COMPLETE) is just a completion marker
TOTAL_STAGES = len(STAGE_NAMES) - 1  # Exclude COMPLETE stage (23 stages: 0-22)

# Delay in seconds to show completion before summary appears
SUMMARY_DISPLAY_DELAY = 0.15


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
        self.current_module = None
        self.current_sub_process = None
        self._closed = False  # Track if progress tracker has been closed
        self._summary_printed = False  # Track if summary has been printed (idempotency)

        # Only show progress for main worker
        # Check if we can use Rich (TTY available and Rich installed)
        # Check both stdout and stderr for TTY since we use stderr for progress
        self.use_rich = (
            is_main_worker and
            RICH_AVAILABLE and
            (sys.stdout.isatty() or sys.stderr.isatty())
        )

        if self.use_rich:
            # Use stderr for progress bar to separate from stdout logging
            # This keeps progress bar visible even when logs flood stdout
            # Create a single console instance to prevent multiple progress bars
            self.console = Console(
                file=sys.stderr,
                force_terminal=True,
                width=None,  # Auto-detect width
                legacy_windows=False
            )
            # Create Progress with only ONE task to ensure single progress bar
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]{task.description}", justify="left"),
                BarColumn(bar_width=None, style="cyan", complete_style="bold cyan", finished_style="bold green"),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%", style="bold"),
                TimeElapsedColumn(),
                TextColumn("•", style="dim"),
                TimeRemainingColumn(),
                console=self.console,
                expand=True,
                refresh_per_second=10,
                transient=True
            )
            self.stage_task = None
            self._header_printed = False
        else:
            self.console = None
            self.progress = None
            self.stage_task = None
            self._header_printed = False

    def __enter__(self) -> 'ApplicationLaunchProgressTracker':
        """
        Context manager entry.
        
        Returns:
            Self for use as context manager
        """
        if self.use_rich and self.progress is not None and self.console is not None:
            try:
                # Start progress context first to ensure single display
                self.progress.__enter__()
                # Create single main stage progress task (only one bar)
                # This ensures only ONE progress bar is displayed
                self.stage_task = self.progress.add_task(
                    f"{STAGE_NAMES[STAGE_SIGNAL_HANDLERS]}",
                    total=TOTAL_STAGES
                )
                # Print header after progress starts (so it appears above the bar)
                self.console.print()
                self.console.print(Rule("[bold cyan]Application Startup Progress[/bold cyan]", style="cyan"))
                self.console.print()
                self._header_printed = True
            except Exception as e:  # pylint: disable=broad-except
                # Log error but don't fail - fall back to logging mode
                logger.warning(
                    "[LaunchProgress] Failed to initialize Rich progress bar: %s",
                    e,
                    exc_info=True
                )
                # Disable Rich mode on error
                self.use_rich = False
                self.progress = None
                self.console = None
                self.stage_task = None

        if not self.use_rich and self.is_main_worker:
            logger.info("[Launch] Starting application initialization...")

        return self

    def kill(self) -> None:
        """
        Forcefully kill the progress bar immediately.
        
        This method forcefully terminates the progress bar without waiting
        for proper cleanup. Use this when you need to immediately stop
        the progress bar, e.g., during error handling or forced shutdown.
        
        This method is idempotent - calling it multiple times is safe.
        Ensures all resources are properly cleaned up even if errors occur.
        """
        # Idempotency check: if already closed, skip cleanup
        if self._closed:
            return

        self._closed = True  # Mark as closed immediately

        # Store references for cleanup
        progress_ref = self.progress
        console_ref = self.console
        task_ref = self.stage_task

        # Clear references early to prevent accidental reuse
        self.stage_task = None
        self.progress = None
        self.console = None

        if self.use_rich and progress_ref:
            try:
                # Forcefully stop and remove the progress task
                if task_ref is not None:
                    try:
                        progress_ref.stop_task(task_ref)
                        progress_ref.remove_task(task_ref)
                    except (KeyError, ValueError, AttributeError) as e:
                        # Task already removed or doesn't exist, log for debugging
                        logger.debug(
                            "[LaunchProgress] Task already removed during kill: %s",
                            e
                        )
                # Forcefully exit the progress context
                try:
                    progress_ref.__exit__(None, None, None)
                except Exception as e:  # pylint: disable=broad-except
                    # Log errors during forced exit for debugging
                    logger.debug(
                        "[LaunchProgress] Error during progress context exit: %s",
                        e,
                        exc_info=True
                    )
            except Exception as e:  # pylint: disable=broad-except
                # Log errors during kill for debugging (non-critical but should be visible)
                logger.warning(
                    "[LaunchProgress] Error during progress bar kill: %s",
                    e,
                    exc_info=True
                )
            finally:
                # Ensure all references are cleared (redundant but safe)
                # This ensures cleanup even if exceptions occur above
                if console_ref:
                    try:
                        # Try to flush console output if possible
                        console_file = getattr(console_ref, '_file', None)
                        if console_file is not None and hasattr(console_file, 'flush'):
                            console_file.flush()
                    except Exception:  # pylint: disable=broad-except
                        pass

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional['TracebackType']
    ) -> None:
        """
        Context manager exit.
        
        Args:
            exc_type: Exception type if exception occurred
            exc_val: Exception value if exception occurred
            exc_tb: Exception traceback if exception occurred
        """
        # Use kill() for consistent cleanup (it's idempotent)
        self.kill()

    def update_stage(
        self,
        stage: int,
        description: Optional[str] = None,
        module: Optional[str] = None,
        sub_process: Optional[str] = None
    ) -> None:
        """
        Update current launch stage.
        
        Args:
            stage: Stage number (use STAGE_* constants, must be 0-23)
            description: Optional custom description
            module: Optional module name (e.g., "LLM Service", "Database")
            sub_process: Optional sub-process name within the module
        """
        # Don't update if progress tracker has been closed
        # This prevents updates after startup completes (e.g., if tracker is reused incorrectly)
        if self._closed:
            logger.debug("[LaunchProgress] Skipping update_stage(%s) - tracker closed (startup completed)", stage)
            return

        # Validate stage number is within valid range (0-23)
        if stage < STAGE_SIGNAL_HANDLERS or stage > STAGE_COMPLETE:
            logger.warning(
                "[LaunchProgress] Invalid stage number %s (valid range: %s-%s), ignoring update",
                stage, STAGE_SIGNAL_HANDLERS, STAGE_COMPLETE
            )
            return

        self.current_stage = stage
        self.current_module = module
        self.current_sub_process = sub_process
        stage_name = description or STAGE_NAMES.get(stage, f"Stage {stage}")

        # Build display description with module and sub-process info
        display_description = stage_name
        if module:
            display_description = f"[cyan]{module}[/cyan] • {stage_name}"
        if sub_process:
            display_description = f"{display_description} ({sub_process})"

        if self.use_rich and self.progress and self.stage_task is not None:
            # Ensure we only update the single progress bar
            # Check that the task still exists in the progress
            try:
                # Calculate completed stages for percentage
                # Stages 0-22 are actual initialization stages (23 stages total)
                # Stage 23 (COMPLETE) is just a completion marker
                # When at stage N, we've completed N+1 stages (stages 0-N inclusive)
                # But for COMPLETE stage, we've completed all TOTAL_STAGES
                if stage == STAGE_COMPLETE:
                    completed = TOTAL_STAGES
                else:
                    # For stages 0-22, completed = stage + 1
                    # Stage 0 means 1 stage completed, stage 22 means 23 stages completed
                    completed = stage + 1

                # Update the single progress bar in place (Rich automatically refreshes)
                # Use bold styling for better visibility
                self.progress.update(
                    self.stage_task,
                    completed=completed,
                    description=f"[bold]{display_description}[/bold]"
                )
            except (KeyError, ValueError) as e:
                # Task was removed or progress context closed, ignore
                logger.debug("[LaunchProgress] Progress update failed (task removed/closed): %s", e)
            except Exception as e:  # pylint: disable=broad-except
                # Log other exceptions but don't fail - progress bar is non-critical
                logger.warning("[LaunchProgress] Progress update failed (non-critical): %s", e, exc_info=True)
        elif self.is_main_worker:
            log_msg = stage_name
            if module:
                log_msg = f"[{module}] {stage_name}"
            if sub_process:
                log_msg = f"{log_msg} ({sub_process})"
            logger.info("[Launch] %s", log_msg)

    def add_error(self, error_message: str) -> None:
        """
        Add an error message to be displayed in the final summary.
        
        Errors are collected during startup and displayed in the completion summary.
        In non-Rich mode, errors are also logged immediately.
        
        Args:
            error_message: Error message to add (will be displayed in summary)
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
        
        Note: Progress bar should be completed before calling this method.
        This method is idempotent - calling it multiple times will only print once.
        """
        # Idempotency check: if summary already printed, skip
        if self._summary_printed:
            logger.debug("[LaunchProgress] Summary already printed, skipping duplicate call")
            return

        if self.use_rich and self.console is not None and self.progress is not None:
            # Complete the progress bar to 100% before printing summary
            # This ensures it shows completion before disappearing (transient=True)
            if self.stage_task is not None:
                self.progress.update(
                    self.stage_task,
                    completed=TOTAL_STAGES,
                    description="[bold green]Complete[/bold green]"
                )
                # Brief delay to ensure completion is visible before summary
                # Note: This is a blocking sleep, but it's acceptable here because:
                # 1. This is called during startup (synchronous phase)
                # 2. The delay is very short (0.15 seconds)
                # 3. It improves UX by showing completion before summary
                # If called from async context, caller should use asyncio.sleep() wrapper
                time.sleep(SUMMARY_DISPLAY_DELAY)

            # Create a panel for the summary to make it stand out
            # Show actual completed stages (not including COMPLETE marker)
            completed_count = TOTAL_STAGES if self.current_stage == STAGE_COMPLETE else self.current_stage + 1
            summary_text = f"Stages completed: [bold green]{completed_count}/{TOTAL_STAGES}[/bold green]"
            if self.errors:
                summary_text += f"\n\n[bold yellow]Warnings ({len(self.errors)}):[/bold yellow]"
                for error in self.errors[:10]:
                    summary_text += f"\n  • {error}"
                if len(self.errors) > 10:
                    summary_text += f"\n  ... and {len(self.errors) - 10} more"

            self.console.print()
            self.console.print(Panel(
                summary_text,
                title="[bold green]✓ APPLICATION LAUNCH COMPLETE[/bold green]",
                border_style="green",
                padding=(1, 2)
            ))
            self.console.print()
        elif self.is_main_worker:
            logger.info("=" * 80)
            logger.info("Application Launch Summary")
            logger.info("=" * 80)
            # Show actual completed stages (not including COMPLETE marker)
            completed_count = TOTAL_STAGES if self.current_stage == STAGE_COMPLETE else self.current_stage + 1
            logger.info("Stages completed: %d/%d", completed_count, TOTAL_STAGES)

            if self.errors:
                logger.warning("Warnings (%d):", len(self.errors))
                for error in self.errors[:10]:
                    logger.warning("  - %s", error)
            if len(self.errors) > 10:
                logger.warning("  ... and %d more", len(self.errors) - 10)

        # Mark summary as printed to prevent duplicate calls
        self._summary_printed = True


class GlobalTrackerManager:
    """
    Thread-safe manager for global tracker instance.
    
    Uses class variables to avoid global statement warnings.
    """
    _instance: Optional['ApplicationLaunchProgressTracker'] = None
    _lock = threading.Lock()


def set_global_tracker_instance(tracker: Optional['ApplicationLaunchProgressTracker']) -> None:
    """
    Set the global tracker instance for easy access and killing.

    Thread-safe operation using a lock to prevent race conditions.

    Args:
        tracker: The progress tracker instance to track globally
    """
    with GlobalTrackerManager._lock:
        GlobalTrackerManager._instance = tracker


def kill_global_progress_bar() -> bool:
    """
    Forcefully kill the global progress bar if it exists.

    This is a standalone function that can be called from anywhere
    to immediately terminate the progress bar, even if the normal
    cleanup path isn't available.

    Thread-safe operation using a lock to prevent race conditions.

    Returns:
        True if progress bar was killed, False if it didn't exist
    """
    with GlobalTrackerManager._lock:
        if GlobalTrackerManager._instance is not None:
            try:
                GlobalTrackerManager._instance.kill()
                GlobalTrackerManager._instance = None
                return True
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "[LaunchProgress] Failed to kill global progress bar: %s",
                    e,
                    exc_info=True
                )
                GlobalTrackerManager._instance = None
                return False
    return False
