"""
Early startup configuration for MindGraph application.

Handles:
- Windows event loop policy setup (required for Playwright)
- Environment file UTF-8 encoding check
- Signal handler registration for graceful shutdown
- Logs directory creation
- Tiktoken encoding file caching (offline loading)
"""

import os
import sys
import asyncio
import signal
import logging
import inspect
from pathlib import Path
from dotenv import load_dotenv
from utils.env_utils import ensure_utf8_env_file
from utils.tiktoken_cache import ensure_tiktoken_cache

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

class _ShutdownEventManager:
    """Manages shutdown event state without using global variables"""
    _shutdown_event = None

    @classmethod
    def get_shutdown_event(cls):
        """Get or create shutdown event for current event loop"""
        try:
            asyncio.get_event_loop()
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
    if os.getenv('UVICORN_WORKER_ID') is not None:
        return False

    if _PSUTIL_AVAILABLE:
        try:
            current_process = psutil.Process()
            process_name = current_process.name().lower()

            # Check if process name indicates reloader
            if 'reload' in process_name or 'watch' in process_name:
                return True

            # Check parent process name
            try:
                parent = current_process.parent()
                if parent:
                    parent_name = parent.name().lower()
                    if 'reload' in parent_name or 'watch' in parent_name:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        except Exception:  # pylint: disable=broad-except
            # Any other error, continue with other checks
            pass

    # Check if we're being imported (not run directly)
    # If __main__ is not in sys.modules, we're being imported
    if '__main__' not in sys.modules:
        # Check call stack to see if we're being imported by uvicorn
        frame = inspect.currentframe()
        if frame:
            try:
                # Go up the call stack to see caller
                caller_frame = frame.f_back
                if caller_frame:
                    caller_module = caller_frame.f_globals.get('__name__', '')
                    # If being imported by uvicorn reloader
                    if 'uvicorn.reload' in caller_module.lower() or 'reload' in caller_module.lower():
                        return True
            finally:
                del frame

    return False


class _BannerManager:
    """Manages banner printing state without using global variables"""
    _banner_printed = False

    @classmethod
    def _should_print_banner(cls) -> bool:
        """
        Determine if we should print the banner.
        
        Banner should only print:
        - In the main process (not workers, not reloader)
        - Once per process (using class variable)
        """
        # Already printed in this process
        if cls._banner_printed:
            return False

        # Skip if we're in Uvicorn reloader process (reloader doesn't serve requests)
        if _is_uvicorn_reloader_process():
            return False

        # Skip if we're a Uvicorn worker (workers have UVICORN_WORKER_ID set)
        # Only print in the main process that spawns workers
        worker_id = os.getenv('UVICORN_WORKER_ID')
        if worker_id is not None:
            # We're a worker process - don't print banner
            # The main process (which spawned us) already printed it
            return False

        return True

    @classmethod
    def print_startup_banner(cls) -> None:
        """
        Print the MindGraph startup banner.
        Only prints once in the main process (not in workers or reloader).
        """
        if not cls._should_print_banner():
            return

        # Read version from VERSION file directly to avoid importing config
        try:
            version_file = Path(__file__).parent.parent.parent.parent / 'VERSION'
            version = version_file.read_text().strip()
        except Exception:  # pylint: disable=broad-except
            version = "0.0.0"

        # Print banner using direct print() to bypass logging system
        print()
        print("    ███╗   ███╗██╗███╗   ██╗██████╗  ██████╗ ██████╗  █████╗ ██████╗ ██╗  ██╗")
        print("    ████╗ ████║██║████╗  ██║██╔══██╗██╔════╝ ██╔══██╗██╔══██╗██╔══██╗██║  ██║")
        print("    ██╔████╔██║██║██╔██╗ ██║██║  ██║██║  ███╗██████╔╝███████║██████╔╝███████║")
        print("    ██║╚██╔╝██║██║██║╚██╗██║██║  ██║██║   ██║██╔══██╗██╔══██║██╔═══╝ ██╔══██║")
        print("    ██║ ╚═╝ ██║██║██║ ╚████║██████╔╝╚██████╔╝██║  ██║██║  ██║██║     ██║  ██║")
        print("    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝")
        print("=" * 80)
        print("    AI-Powered Visual Thinking Tools for K12 Education")
        print(f"    Version {version} | 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)")
        print("=" * 80)
        print()

        # Mark banner as printed in this process
        cls._banner_printed = True


def _print_startup_banner() -> None:
    """Print the MindGraph startup banner"""
    _BannerManager.print_startup_banner()


def setup_early_configuration():
    """
    Perform early configuration setup that must happen before other initialization.
    
    This includes:
    - Banner display (first thing shown)
    - Windows event loop policy setup (required for Playwright)
    - Environment file UTF-8 encoding check and loading
    - Signal handler registration
    - Logs directory creation
    """
    # Print banner FIRST before any other operations
    _print_startup_banner()

    # Fix for Windows: Set event loop policy to support subprocesses (required for Playwright)
    # MUST be set before any event loop is created (before Uvicorn starts)
    if sys.platform == 'win32':
        try:
            current_policy = asyncio.get_event_loop_policy()
            if not isinstance(current_policy, asyncio.WindowsProactorEventLoopPolicy):
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                logging.info("Windows: Set event loop policy to WindowsProactorEventLoopPolicy for Playwright support")
        except Exception:  # pylint: disable=broad-except
            # If we can't check/set, try to set it anyway
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                logging.info("Windows: Set event loop policy to WindowsProactorEventLoopPolicy (unconditional)")
            except Exception as e2:  # pylint: disable=broad-except
                logging.warning("Windows: Could not set event loop policy: %s", e2)

    # Ensure .env file is UTF-8 encoded before loading
    ensure_utf8_env_file()

    # Load environment variables
    env_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), '.env')
    env_file_exists = os.path.exists(env_file_path)
    load_dotenv()

    # Diagnostic: Log CHUNKING_ENGINE value at startup (before logger setup)
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
    try:
        ensure_tiktoken_cache()
    except Exception as e:  # pylint: disable=broad-except
        # Non-critical: tiktoken will download files automatically if cache fails
        print(f"[Startup] Warning: Could not setup tiktoken cache: {e}")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
