"""
Celery Application Configuration
Author: lycosa9527
Made by: MindSpring Team

Celery app for background task processing (document processing, etc.)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import logging.handlers
import os
import time

from celery.app import Celery
from celery.signals import worker_process_init, worker_ready
from dotenv import load_dotenv

from config.settings import config
from services.infrastructure.http.error_handler import LLMServiceError
from services.llm import llm_service
from services.redis.redis_client import (
    RedisStartupError,
    init_redis_sync,
    is_redis_available
)


# Load environment variables from .env file
# This ensures Celery workers have access to all environment variables
load_dotenv()

# Configure Celery logging to match application format
class UnifiedFormatter(logging.Formatter):
    """
    Unified formatter matching main.py's format.
    Format: [HH:MM:SS] LEVEL | MODULE | [PID] message
    """

    COLORS = {
        'DEBUG': '\033[37m',      # Gray
        'INFO': '\033[36m',       # Cyan
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m',
        'BOLD': '\033[1m'
    }

    def format(self, record):
        # Timestamp: HH:MM:SS
        timestamp = self.formatTime(record, '%H:%M:%S')

        # Level abbreviation
        level_name = record.levelname
        if level_name == 'CRITICAL':
            level_name = 'CRIT'
        elif level_name == 'WARNING':
            level_name = 'WARN'

        color = self.COLORS.get(level_name, '')
        reset = self.COLORS['RESET']

        if level_name == 'CRIT':
            colored_level = f"{self.COLORS['BOLD']}{color}{level_name.ljust(5)}{reset}"
        else:
            colored_level = f"{color}{level_name.ljust(5)}{reset}"

        # Source abbreviation - handle Celery-specific loggers
        source = record.name
        if 'celery' in source.lower():
            if 'worker' in source.lower() or 'mainprocess' in source.lower():
                source = 'CELE'
            elif 'task' in source.lower():
                source = 'TASK'
            elif 'forkpoolworker' in source.lower():
                # Extract worker number from ForkPoolWorker-1, ForkPoolWorker-2, etc.
                source = 'CELE'
            else:
                source = 'CELE'
        elif source.startswith('services'):
            source = 'SERV'
        elif source.startswith('clients'):
            source = 'CLIE'
        elif source.startswith('config'):
            source = 'CONF'
        elif source.startswith('routers'):
            source = 'API'
        elif source == '__main__':
            source = 'MAIN'
        else:
            source = source[:4].upper()

        source = source.ljust(4)

        # Process ID
        pid = record.process if hasattr(record, 'process') else os.getpid()

        return f"[{timestamp}] {colored_level} | {source} | [{pid}] {record.getMessage()}"

# Configure Celery logging
def setup_celery_logging():
    """Configure Celery to use unified logging format."""
    # Get root logger
    root_logger = logging.getLogger()

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler with unified formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(UnifiedFormatter())

    # Create file handler to write to logs/app.log (same as main application)
    # Ensure logs directory exists
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    # Use RotatingFileHandler for log rotation (10MB max, keep 10 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setFormatter(UnifiedFormatter())

    # Configure Celery loggers - including all variants
    celery_loggers = [
        'celery',
        'celery.worker',
        'celery.task',
        'celery.worker.strategy',
        'celery.beat',
        'celery.app',
        'celery.app.trace',
    ]

    for logger_name in celery_loggers:
        celery_logger = logging.getLogger(logger_name)
        celery_logger.handlers = []
        celery_logger.addHandler(console_handler)
        celery_logger.addHandler(file_handler)  # Add file handler
        celery_logger.setLevel(logging.DEBUG)  # Full verbose logging
        celery_logger.propagate = False

    # Configure root logger to catch all messages
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)  # Add file handler
    root_logger.setLevel(logging.DEBUG)  # Full verbose logging

    # Also configure any existing logger that starts with 'celery'
    # This catches MainProcess and ForkPoolWorker loggers
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        if isinstance(logger_name, str) and 'celery' in logger_name.lower():
            celery_logger = logging.getLogger(logger_name)
            celery_logger.handlers = []
            celery_logger.addHandler(console_handler)
            celery_logger.addHandler(file_handler)  # Add file handler
            celery_logger.setLevel(logging.DEBUG)  # Full verbose logging
            celery_logger.propagate = False

    # Set all application loggers to DEBUG for verbose logging
    app_loggers = [
        'services',
        'llm_chunking',
        'tasks',
        'clients',
        'agents',
        'routers',
        'utils',
        'config',
    ]
    for logger_prefix in app_loggers:
        app_logger = logging.getLogger(logger_prefix)
        app_logger.setLevel(logging.DEBUG)
        app_logger.propagate = True  # Let it propagate to root

# Setup logging before creating Celery app
setup_celery_logging()

# Module-level logger
logger = logging.getLogger(__name__)

# Error message width (matching Redis format)
_ERROR_WIDTH = 70


class CeleryStartupError(Exception):
    """
    Raised when Celery worker is not available during startup.

    This is a controlled startup failure - the error message has already
    been logged with instructions. Catching this exception should exit
    cleanly without logging additional tracebacks.
    """


def _log_celery_error(title: str, details: list[str]) -> None:
    """
    Log a Celery error with clean, professional formatting.

    Args:
        title: Error title (e.g., "CELERY WORKER NOT AVAILABLE")
        details: List of detail lines to display
    """
    separator = "=" * _ERROR_WIDTH

    lines = [
        "",
        separator,
        title.center(_ERROR_WIDTH),
        separator,
        "",
    ]
    lines.extend(details)
    lines.extend(["", separator, ""])

    error_msg = "\n".join(lines)
    logger.critical(error_msg)


# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_DB = os.getenv('REDIS_CELERY_DB', '1')  # Use DB 1 for Celery (DB 0 for caching)

BROKER_URL = os.getenv('CELERY_BROKER_URL', f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')
BACKEND_URL = os.getenv('CELERY_RESULT_BACKEND', f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')

# Create Celery app
celery_app = Celery(
    'mindgraph',
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=['tasks.knowledge_space_tasks'],  # Register tasks
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes (reliability)
    task_reject_on_worker_lost=True,  # Requeue if worker crashes

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker (for long-running tasks)
    worker_concurrency=2,  # 2 concurrent tasks per worker

    # Result settings
    result_expires=3600,  # Results expire after 1 hour

    # Task queues (like Dify's queue isolation)
    task_routes={
        'knowledge_space.*': {'queue': 'knowledge'},
    },

    # Default queue
    task_default_queue='default',
)


def init_celery_worker_check() -> bool:
    """
    Check if Celery worker is available (synchronous version for startup).

    Celery is REQUIRED. Application will exit if worker is not available.
    Uses retry logic with exponential backoff to handle workers that are starting up.

    Returns:
        True if Celery worker is available.

    Raises:
        CeleryStartupError: Application will exit if Celery worker is unavailable.
    """
    logger.info("[Celery] Checking Celery worker availability...")

    # Retry configuration
    max_retries = int(os.getenv('CELERY_CHECK_MAX_RETRIES', '5'))
    initial_delay = float(os.getenv('CELERY_CHECK_INITIAL_DELAY', '1.0'))
    max_delay = float(os.getenv('CELERY_CHECK_MAX_DELAY', '16.0'))

    last_exception = None
    for attempt in range(max_retries):
        try:
            # Use Celery's inspect API to check for active workers
            # This requires Redis to be available (already validated)
            inspect = celery_app.control.inspect(timeout=2.0)
            active_workers = inspect.active()

            if active_workers is None:
                # No workers found or connection failed - retry
                if attempt < max_retries - 1:
                    delay = min(initial_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "[Celery] No workers found (attempt %d/%d). "
                        "Retrying in %.1f seconds...",
                        attempt + 1, max_retries, delay
                    )
                    time.sleep(delay)
                    last_exception = None
                    continue
                # Final attempt failed
                _log_celery_error(
                    title="CELERY WORKER NOT AVAILABLE",
                    details=[
                        "No Celery workers are running or cannot connect to workers.",
                        "",
                        f"Checked {max_retries} times with retries.",
                        "",
                        "MindGraph requires Celery worker. Please start Celery worker:",
                        "",
                        "  celery -A config.celery worker --loglevel=info",
                        "",
                        "Or use the server launcher which starts Celery automatically:",
                        "  python main.py",
                        "",
                        "Ensure Redis is running (required for Celery broker).",
                    ]
                )
                raise CeleryStartupError("Celery worker not available") from None

            if not active_workers:
                # Empty dict means no workers - retry
                if attempt < max_retries - 1:
                    delay = min(initial_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "[Celery] No active workers found (attempt %d/%d). "
                        "Retrying in %.1f seconds...",
                        attempt + 1, max_retries, delay
                    )
                    time.sleep(delay)
                    last_exception = None
                    continue
                # Final attempt failed
                _log_celery_error(
                    title="CELERY WORKER NOT AVAILABLE",
                    details=[
                        "No active Celery workers found.",
                        "",
                        f"Checked {max_retries} times with retries.",
                        "",
                        "MindGraph requires Celery worker. Please start Celery worker:",
                        "",
                        "  celery -A config.celery worker --loglevel=info",
                        "",
                        "Or use the server launcher which starts Celery automatically:",
                        "  python main.py",
                    ]
                )
                raise CeleryStartupError("No active Celery workers found") from None

            # Success - workers found
            worker_count = len(active_workers)
            if attempt > 0:
                logger.info(
                    "[Celery] Found %d active worker(s) after %d retry attempt(s)",
                    worker_count, attempt
                )
            else:
                logger.info("[Celery] Found %d active worker(s)", worker_count)
            return True

        except CeleryStartupError:
            # Re-raise our custom exception immediately (don't retry)
            raise
        except Exception as exc:
            # Connection error or other unexpected error - retry
            last_exception = exc
            if attempt < max_retries - 1:
                delay = min(initial_delay * (2 ** attempt), max_delay)
                logger.warning(
                    "[Celery] Worker check failed: %s (attempt %d/%d). "
                    "Retrying in %.1f seconds...",
                    exc, attempt + 1, max_retries, delay
                )
                time.sleep(delay)
                continue
            # Final attempt failed
            _log_celery_error(
                title="CELERY WORKER CHECK FAILED",
                details=[
                    f"Failed to check Celery worker availability: {exc}",
                    "",
                    f"Checked {max_retries} times with retries.",
                    "",
                    "MindGraph requires Celery worker. Please ensure:",
                    "",
                    "  1. Redis is running (required for Celery broker)",
                    "  2. Celery worker is started:",
                    "     celery -A config.celery worker --loglevel=info",
                    "",
                    "Or use the server launcher which starts Celery automatically:",
                    "  python main.py",
                ]
            )
            raise CeleryStartupError(f"Failed to check Celery worker: {exc}") from exc

    # Should never reach here, but handle it just in case
    if last_exception:
        raise CeleryStartupError(f"Failed to check Celery worker after {max_retries} attempts") from last_exception
    raise CeleryStartupError(f"Failed to check Celery worker after {max_retries} attempts")


# Initialize services in Celery workers
# This ensures MindChunk can use LLM services in worker processes
def _init_worker_services():
    """
    Initialize services when Celery worker process starts.

    This ensures:
    - Redis is initialized (for caching, rate limiting)
    - LLM service is initialized (for MindChunk)
    """
    # Initialize Redis first (LLM service may depend on it)
    worker_logger = logging.getLogger(__name__)
    try:
        if not is_redis_available():
            worker_logger.info("[Celery] Initializing Redis in worker process...")
            init_redis_sync()
            worker_logger.info("[Celery] ✓ Redis initialized in worker process")
        else:
            worker_logger.debug("[Celery] Redis already initialized in worker process")
    except RedisStartupError as e:
        worker_logger.warning("[Celery] Redis initialization failed: %s", e)
    except (OSError, ConnectionError) as e:
        worker_logger.warning("[Celery] Redis connection error: %s", e)


    # Initialize LLM service for MindChunk
    try:
        # Check if API key is configured
        if not config.QWEN_API_KEY:
            worker_logger.error(
                "[Celery] QWEN_API_KEY not configured. "
                "LLM service cannot be initialized. MindChunk will fall back to semchunk."
            )
            return

        worker_logger.info("[Celery] Checking LLM service initialization...")
        worker_logger.debug("[Celery] QWEN_API_KEY configured: %s...", config.QWEN_API_KEY[:10])
        worker_logger.debug("[Celery] DASHSCOPE_API_URL: %s", config.DASHSCOPE_API_URL)

        if not llm_service.client_manager.is_initialized():
            worker_logger.info("[Celery] Initializing LLM service in worker process...")
            llm_service.initialize()

            # Verify initialization succeeded
            if llm_service.client_manager.is_initialized():
                worker_logger.info("[Celery] ✓ LLM service initialized successfully in worker process")
                worker_logger.debug("[Celery] Available models: %s", llm_service.client_manager.get_available_models())
            else:
                worker_logger.error("[Celery] ✗ LLM service initialization failed - is_initialized() returned False")
        else:
            worker_logger.info("[Celery] LLM service already initialized in worker process")
    except ImportError as e:
        worker_logger.error(
            "[Celery] Failed to import LLM service dependencies: %s. "
            "MindChunk will not be available.",
            e
        )
    except LLMServiceError as e:
        worker_logger.error(
            "[Celery] LLM service initialization error: %s. "
            "MindChunk will not be available.",
            e
        )
    except (OSError, ConnectionError) as e:
        worker_logger.error(
            "[Celery] LLM service connection error: %s. "
            "MindChunk will not be available.",
            e
        )
    except RuntimeError as e:
        worker_logger.error(
            "[Celery] LLM service runtime error: %s. "
            "MindChunk will not be available.",
            e
        )

# Register signal handlers for worker initialization
@worker_process_init.connect
def on_worker_process_init(_sender=None, **_kwargs):
    """Called when worker process starts."""
    # Reconfigure logging in worker process to use unified format
    setup_celery_logging()

    # Use module-level logger (already defined at line 188)
    worker_name = os.environ.get('CELERY_WORKER_NAME', 'unknown')
    pid = os.getpid()

    logger.info("[Celery] ===== ForkPoolWorker process started: PID=%s, Worker=%s =====", pid, worker_name)
    logger.info("[Celery] Initializing services in worker process...")

    _init_worker_services()

    logger.info("[Celery] ===== ForkPoolWorker process ready: PID=%s =====", pid)

@worker_ready.connect
def on_worker_ready(_sender=None, **_kwargs):
    """
    Called when worker is ready to accept tasks.

    Note: This runs in MainProcess, not in worker processes.
    Worker processes initialize services via worker_process_init signal.
    """
    ready_logger = logging.getLogger(__name__)
    ready_logger.info("[Celery] Worker ready - services initialized in worker processes")

    # Note: LLM service initialization happens in worker_process_init signal
    # which runs in each ForkPoolWorker process, not in MainProcess.
    # MainProcess doesn't need LLM service - only worker processes do.

# For running worker directly: celery -A config.celery worker --loglevel=info
if __name__ == '__main__':
    celery_app.start()
