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

from celery.app import Celery
from celery.signals import worker_process_init, worker_ready
from dotenv import load_dotenv

from config.settings import config
from services.infrastructure.error_handler import LLMServiceError
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
        logger = logging.getLogger(logger_name)
        logger.handlers = []
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)  # Add file handler
        logger.setLevel(logging.DEBUG)  # Full verbose logging
        logger.propagate = False

    # Configure root logger to catch all messages
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)  # Add file handler
    root_logger.setLevel(logging.DEBUG)  # Full verbose logging

    # Also configure any existing logger that starts with 'celery'
    # This catches MainProcess and ForkPoolWorker loggers
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        if isinstance(logger_name, str) and 'celery' in logger_name.lower():
            logger = logging.getLogger(logger_name)
            logger.handlers = []
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)  # Add file handler
            logger.setLevel(logging.DEBUG)  # Full verbose logging
            logger.propagate = False

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
        logger = logging.getLogger(logger_prefix)
        logger.setLevel(logging.DEBUG)
        logger.propagate = True  # Let it propagate to root

# Setup logging before creating Celery app
setup_celery_logging()

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

# Initialize services in Celery workers
# This ensures MindChunk can use LLM services in worker processes
def _init_worker_services():
    """
    Initialize services when Celery worker process starts.

    This ensures:
    - Redis is initialized (for caching, rate limiting)
    - LLM service is initialized (for MindChunk)
    """
    logger = logging.getLogger(__name__)

    # Initialize Redis first (LLM service may depend on it)
    try:
        if not is_redis_available():
            logger.info("[Celery] Initializing Redis in worker process...")
            init_redis_sync()
            logger.info("[Celery] ✓ Redis initialized in worker process")
        else:
            logger.debug("[Celery] Redis already initialized in worker process")
    except RedisStartupError as e:
        logger.warning("[Celery] Redis initialization failed: %s", e)
    except (OSError, ConnectionError) as e:
        logger.warning("[Celery] Redis connection error: %s", e)


    # Initialize LLM service for MindChunk
    try:
        # Check if API key is configured
        if not config.QWEN_API_KEY:
            logger.error(
                "[Celery] QWEN_API_KEY not configured. "
                "LLM service cannot be initialized. MindChunk will fall back to semchunk."
            )
            return

        logger.info("[Celery] Checking LLM service initialization...")
        logger.debug("[Celery] QWEN_API_KEY configured: %s...", config.QWEN_API_KEY[:10])
        logger.debug("[Celery] DASHSCOPE_API_URL: %s", config.DASHSCOPE_API_URL)

        if not llm_service.client_manager.is_initialized():
            logger.info("[Celery] Initializing LLM service in worker process...")
            llm_service.initialize()

            # Verify initialization succeeded
            if llm_service.client_manager.is_initialized():
                logger.info("[Celery] ✓ LLM service initialized successfully in worker process")
                logger.debug("[Celery] Available models: %s", llm_service.client_manager.get_available_models())
            else:
                logger.error("[Celery] ✗ LLM service initialization failed - is_initialized() returned False")
        else:
            logger.info("[Celery] LLM service already initialized in worker process")
    except ImportError as e:
        logger.error(
            "[Celery] Failed to import LLM service dependencies: %s. "
            "MindChunk will not be available.",
            e
        )
    except LLMServiceError as e:
        logger.error(
            "[Celery] LLM service initialization error: %s. "
            "MindChunk will not be available.",
            e
        )
    except (OSError, ConnectionError) as e:
        logger.error(
            "[Celery] LLM service connection error: %s. "
            "MindChunk will not be available.",
            e
        )
    except RuntimeError as e:
        logger.error(
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

    # Get logger after setup
    logger = logging.getLogger(__name__)
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
    logger = logging.getLogger(__name__)
    logger.info("[Celery] Worker ready - services initialized in worker processes")

    # Note: LLM service initialization happens in worker_process_init signal
    # which runs in each ForkPoolWorker process, not in MainProcess.
    # MainProcess doesn't need LLM service - only worker processes do.

# For running worker directly: celery -A config.celery worker --loglevel=info
if __name__ == '__main__':
    celery_app.start()
