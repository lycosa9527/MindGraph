"""
Early startup configuration for MindGraph application.

Handles:
- Windows event loop policy setup (required for Playwright)
- Environment file UTF-8 encoding check
- Signal handler registration for graceful shutdown
- Logs directory creation
- Tiktoken encoding file caching (offline loading)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import inspect
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.env_utils import ensure_utf8_env_file
from utils.tiktoken_cache import ensure_tiktoken_cache

logger = logging.getLogger(__name__)

psutil: Any = None
_PSUTIL_AVAILABLE = False
try:
    import psutil as _psutil

    psutil = _psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    pass

# Set by server_launcher.run_server() before Uvicorn spawns workers; inherited by child
# processes so we skip duplicate [Startup] prints on re-import of main.
MINDGRAPH_LAUNCHER_PID_ENV = "MINDGRAPH_LAUNCHER_PID"


class _UvicornProcessHints:
    """Detect Uvicorn/launcher child-process context for startup logs."""

    @staticmethod
    def is_launched_child() -> bool:
        """True when this process is a Uvicorn worker child of the launcher process."""
        raw = os.environ.get(MINDGRAPH_LAUNCHER_PID_ENV)
        if not raw:
            return False
        return str(os.getpid()) != raw


class _ShutdownEventManager:
    """Manages shutdown event state without using global variables"""

    _shutdown_event = None

    @classmethod
    def get_shutdown_event(cls):
        """Get or create shutdown event for current event loop"""
        try:
            asyncio.get_running_loop()
            if cls._shutdown_event is None:
                cls._shutdown_event = asyncio.Event()
            return cls._shutdown_event
        except RuntimeError:
            return None

    @classmethod
    def handle_shutdown_signal(cls, _signum, _frame):
        """Handle shutdown signals gracefully (SIGINT, SIGTERM)"""
        event = cls.get_shutdown_event()
        if event and not event.is_set():
            event.set()


def _get_shutdown_event():
    """Get or create shutdown event for current event loop"""
    return _ShutdownEventManager.get_shutdown_event()


def _handle_shutdown_signal(_signum, _frame) -> None:
    """Handle shutdown signals gracefully (SIGINT, SIGTERM)"""
    _ShutdownEventManager.handle_shutdown_signal(_signum, _frame)


def _is_uvicorn_reloader_process() -> bool:
    """
    Check if we're running in Uvicorn's reloader process.

    Uvicorn reloader process can be detected by:
    - Process name contains 'reload' or 'watch'
    - Or we're being imported by the reloader (check call stack)
    - Or check if parent process is the reloader
    - Workers have UVICORN_WORKER_ID set, reloader doesn't (but initial process also doesn't)
    """
    # If UVICORN_WORKER_ID is set, we're definitely a worker (not reloader)
    if os.getenv("UVICORN_WORKER_ID") is not None:
        return False

    if _PSUTIL_AVAILABLE and psutil is not None:
        try:
            current_process = psutil.Process()
            process_name = current_process.name().lower()

            # Check if process name indicates reloader
            if "reload" in process_name or "watch" in process_name:
                return True

            # Check parent process name
            try:
                parent = current_process.parent()
                if parent:
                    parent_name = parent.name().lower()
                    if "reload" in parent_name or "watch" in parent_name:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.debug("Uvicorn reloader process detection failed: %s", exc)

    # Check if we're being imported (not run directly)
    # If __main__ is not in sys.modules, we're being imported
    if "__main__" not in sys.modules:
        # Check call stack to see if we're being imported by uvicorn
        frame = inspect.currentframe()
        if frame:
            try:
                # Go up the call stack to see caller
                caller_frame = frame.f_back
                if caller_frame:
                    caller_module = caller_frame.f_globals.get("__name__", "")
                    # If being imported by uvicorn reloader
                    if "uvicorn.reload" in caller_module.lower() or "reload" in caller_module.lower():
                        return True
            finally:
                del frame

    return False


# Do not delete this MindGraph ASCII banner. It must show at application launch.
_MINDGRAPH_ASCII_BANNER = (
    "    ███╗   ███╗██╗███╗   ██╗██████╗  ██████╗ ██████╗  █████╗ ██████╗ ██╗  ██╗",
    "    ████╗ ████║██║████╗  ██║██╔══██╗██╔════╝ ██╔══██╗██╔══██╗██╔══██╗██║  ██║",
    "    ██╔████╔██║██║██╔██╗ ██║██║  ██║██║  ███╗██████╔╝███████║██████╔╝███████║",
    "    ██║╚██╔╝██║██║██║╚██╗██║██║  ██║██║   ██║██╔══██╗██╔══██║██╔═══╝ ██╔══██║",
    "    ██║ ╚═╝ ██║██║██║ ╚████║██████╔╝╚██████╔╝██║  ██║██║  ██║██║     ██║  ██║",
    "    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝",
)


def mindgraph_startup_banner_lines() -> tuple[str, ...]:
    """Launch banner lines, including the version. Do not remove."""
    try:
        version_file = Path(__file__).resolve().parents[3] / "VERSION"
        version = version_file.read_text(encoding="utf-8").strip()
    except BACKGROUND_INFRA_ERRORS:
        version = "0.0.0"
    return (
        *_MINDGRAPH_ASCII_BANNER,
        "=" * 80,
        "    AI-Powered Visual Thinking Tools for K12 Education",
        f"    Version {version} | 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)",
        "=" * 80,
    )


def setup_early_configuration():
    """
    Perform early configuration setup that must happen before other initialization.

    This includes:
    - Windows event loop policy setup (required for Playwright)
    - Environment file UTF-8 encoding check and loading
    - Signal handler registration
    - Logs directory creation
    """
    # Only print startup messages from main process (not reloader, not workers)
    # Check if we should skip startup messages
    worker_id = os.getenv("UVICORN_WORKER_ID")
    is_reloader = _is_uvicorn_reloader_process()
    should_log_startup = not is_reloader and worker_id is None and not _UvicornProcessHints.is_launched_child()

    # Do not print the ASCII banner here. Lifespan logs it once when launch completes.
    # A second print from this process would show two banners at startup.

    # Windows event loop: psycopg async requires SelectorEventLoop; Proactor is only
    # needed for Playwright subprocesses (set WINDOWS_PROACTOR_EVENT_LOOP=1 if PNG export fails).
    # MUST be set before any event loop is created (before Uvicorn starts)
    if sys.platform == "win32":
        use_proactor = os.getenv("WINDOWS_PROACTOR_EVENT_LOOP", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        try:
            if use_proactor:
                policy: asyncio.AbstractEventLoopPolicy = asyncio.WindowsProactorEventLoopPolicy()
                policy_name = "WindowsProactorEventLoopPolicy"
            else:
                policy = asyncio.WindowsSelectorEventLoopPolicy()
                policy_name = "WindowsSelectorEventLoopPolicy"
            if not isinstance(asyncio.get_event_loop_policy(), type(policy)):
                asyncio.set_event_loop_policy(policy)
                if should_log_startup:
                    logging.debug("Windows: Set event loop policy to %s", policy_name)
        except BACKGROUND_INFRA_ERRORS as e:
            if should_log_startup:
                logging.warning("Windows: Could not set event loop policy: %s", e)

    # Ensure .env file is UTF-8 encoded before loading
    ensure_utf8_env_file()

    # Load environment variables
    env_file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        ".env",
    )
    env_file_exists = os.path.exists(env_file_path)
    load_dotenv()

    # Diagnostic: Log CHUNKING_ENGINE value at startup (DEBUG level only)
    # Use print because logging is not configured yet (setup_logging runs after this)
    _log_debug = os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG" or os.getenv("DEBUG", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if should_log_startup and _log_debug:
        chunking_engine_startup = os.getenv("CHUNKING_ENGINE", "not set (default: semchunk)")
        print(f"[Startup] .env file exists: {env_file_exists} at {env_file_path}")
        print(f"[Startup] CHUNKING_ENGINE environment variable: {chunking_engine_startup}")
        if chunking_engine_startup.lower() == "mindchunk":
            print("[Startup] ✓ MindChunk is ENABLED - LLM-based chunking will be used")
        else:
            print(f"[Startup] Using chunking engine: {chunking_engine_startup}")

    # Create logs directory
    os.makedirs("logs", exist_ok=True)

    # Setup tiktoken encoding file cache (must be before any tiktoken imports)
    # This downloads encoding files locally to avoid repeated downloads
    # Uses Redis lock internally to ensure only one worker checks/updates cache
    try:
        ensure_tiktoken_cache()
    except BACKGROUND_INFRA_ERRORS as e:
        # Non-critical: tiktoken will download files automatically if cache fails
        if should_log_startup:
            logging.warning("[Startup] Could not setup tiktoken cache: %s", e)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
