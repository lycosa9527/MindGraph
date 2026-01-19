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
from dotenv import load_dotenv
from utils.env_utils import ensure_utf8_env_file
from utils.tiktoken_cache import ensure_tiktoken_cache

# Global flag to track shutdown state
_SHUTDOWN_EVENT = None  # pylint: disable=global-statement


def _get_shutdown_event():
    """Get or create shutdown event for current event loop"""
    global _SHUTDOWN_EVENT  # pylint: disable=global-statement
    try:
        asyncio.get_event_loop()
        if _SHUTDOWN_EVENT is None:
            _SHUTDOWN_EVENT = asyncio.Event()
        return _SHUTDOWN_EVENT
    except RuntimeError:
        return None


def _handle_shutdown_signal(_signum, _frame) -> None:
    """Handle shutdown signals gracefully (SIGINT, SIGTERM)"""
    event = _get_shutdown_event()
    if event and not event.is_set():
        event.set()


def setup_early_configuration():
    """
    Perform early configuration setup that must happen before other initialization.
    
    This includes:
    - Windows event loop policy setup (required for Playwright)
    - Environment file UTF-8 encoding check and loading
    - Signal handler registration
    - Logs directory creation
    """
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
    env_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    ENV_FILE_EXISTS = os.path.exists(env_file_path)
    load_dotenv()

    # Diagnostic: Log CHUNKING_ENGINE value at startup (before logger setup)
    chunking_engine_startup = os.getenv("CHUNKING_ENGINE", "not set (default: semchunk)")
    print(f"[Startup] .env file exists: {ENV_FILE_EXISTS} at {env_file_path}")
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
