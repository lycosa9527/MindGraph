"""
MindGraph - AI-Powered Graph Generation Application (FastAPI)
==============================================================

Modern async web application for AI-powered diagram generation.

Version: See VERSION file (centralized version management)
Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License

Features:
- Full async/await support for 4,000+ concurrent SSE connections
- FastAPI with Pydantic models for type safety
- Uvicorn ASGI server (Windows + Ubuntu compatible)
- Auto-generated OpenAPI documentation at /docs
- Comprehensive logging, middleware, and business logic

Status: Production Ready
"""

# Standard library imports
import sys
import asyncio

# Third-party imports
from fastapi import FastAPI

# First-party imports
from config.settings import config
from routers import (
    pages, cache, api, node_palette, auth, admin_env, admin_logs,
    admin_realtime, voice, update_notification, tab_mode,
    public_dashboard, school_zone, askonce, debateverse, vue_spa
)
from routers.health import router as health_router
from services.infrastructure.startup import setup_early_configuration
from services.infrastructure.logging_config import setup_logging
from services.infrastructure.lifespan import lifespan
from services.infrastructure.middleware import setup_middleware
from services.infrastructure.exception_handlers import setup_exception_handlers
from services.infrastructure.port_manager import check_port_available, cleanup_stale_process, ShutdownErrorFilter
from services.infrastructure.spa_handler import setup_vue_spa, is_dev_mode

# Early configuration setup (must happen before logging)
setup_early_configuration()

# Setup logging (must happen early, before other modules use logger)
logger = setup_logging()

# ============================================================================
# FASTAPI APPLICATION INITIALIZATION
# ============================================================================

app = FastAPI(
    title="MindGraph API",
    description="AI-Powered Graph Generation with FastAPI + Uvicorn",
    version=config.VERSION,
    # Disable Swagger UI in production for security (only enable in DEBUG mode)
    docs_url="/docs" if config.DEBUG else None,
    redoc_url="/redoc" if config.DEBUG else None,
    lifespan=lifespan
)

# ============================================================================
# MIDDLEWARE & EXCEPTION HANDLERS
# ============================================================================

setup_middleware(app)
setup_exception_handlers(app)

# ============================================================================
# STATIC FILES AND VUE SPA
# ============================================================================

# Vue SPA setup (v5.0.0+)
# In production: Serve Vue app from frontend/dist/
# In development: Vite dev server handles frontend on port 3000

# Setup Vue SPA - mounts /assets from frontend/dist/assets/
_VUE_SPA_ENABLED = setup_vue_spa(app)

if _VUE_SPA_ENABLED:
    logger.info("Vue SPA mode: Frontend served from frontend/dist/")
elif not is_dev_mode():
    # Only warn in production - in dev mode, Vite handles frontend
    logger.warning("Vue SPA not available - run 'npm run build' in frontend/ directory")

# ============================================================================
# ROUTER REGISTRATION
# ============================================================================

# Health check endpoints
app.include_router(health_router)

# Vue SPA handles all page routes (v5.0.0+)
app.include_router(vue_spa.router)
# Authentication & utility routes (loginByXz, favicon)
app.include_router(pages.router)
app.include_router(cache.router)
app.include_router(api.router)
app.include_router(node_palette.router)  # Node Palette endpoints
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])  # Authentication system
app.include_router(admin_env.router)  # Admin environment settings management
app.include_router(admin_logs.router)  # Admin log streaming
app.include_router(admin_realtime.router)  # Admin realtime user activity monitoring
app.include_router(voice.router)  # VoiceAgent (real-time voice conversation)
app.include_router(update_notification.router)  # Update notification system
app.include_router(tab_mode.router)  # Tab Mode (autocomplete and expansion)
# Public dashboard endpoints
app.include_router(public_dashboard.router, prefix="/api/public", tags=["Public Dashboard"])
app.include_router(school_zone.router)  # School Zone (organization-scoped sharing)
app.include_router(askonce.router)  # AskOnce (多应) - Multi-LLM streaming chat
# DebateVerse (论境) - US-style debate system
app.include_router(debateverse.router)

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn  # pylint: disable=import-outside-toplevel

    # CRITICAL FIX for Windows: Set event loop policy to support subprocesses
    # Playwright requires subprocess support, which SelectorEventLoop doesn't provide on Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        logger.info("Windows detected: Set event loop policy to WindowsProactorEventLoopPolicy for Playwright support")

    # Print configuration summary
    config.print_config_summary()

    logger.info("=" * 80)
    logger.info("Starting FastAPI application with Uvicorn")
    logger.info("Server: http://%s:%s", config.HOST, config.PORT)
    logger.info("API Docs: http://%s:%s/docs", config.HOST, config.PORT)

    # Pre-flight port availability check
    logger.info("Checking port availability...")
    is_available, pid_using_port = check_port_available(config.HOST, config.PORT)

    if not is_available:
        logger.warning("⚠️  Port %s is already in use", config.PORT)

        if pid_using_port:
            logger.warning("Process %s is using the port", pid_using_port)

            # Attempt automatic cleanup
            if cleanup_stale_process(pid_using_port, config.PORT):
                logger.info("✅ Port cleanup successful, proceeding with startup...")
            else:
                logger.error("=" * 80)
                logger.error("❌ Cannot start server - port %s is still in use", config.PORT)
                logger.error("💡 Manual cleanup required:")
                if sys.platform == 'win32':
                    logger.error("   Windows: taskkill /F /PID %s", pid_using_port)
                else:
                    logger.error("   Linux/Mac: kill -9 %s", pid_using_port)
                logger.error("=" * 80)
                sys.exit(1)
        else:
            logger.error("=" * 80)
            logger.error("❌ Cannot start server - port %s is in use", config.PORT)
            logger.error("💡 Could not detect the process using the port")
            logger.error("   Please check manually and free the port")
            logger.error("=" * 80)
            sys.exit(1)
    else:
        logger.info("✅ Port %s is available", config.PORT)

    if config.DEBUG:
        logger.warning("⚠️  Reload mode enabled - may cause slow shutdown (use Ctrl+C twice if needed)")
    logger.info("=" * 80)

    # Install stderr filter to suppress multiprocessing shutdown tracebacks
    original_stderr = sys.stderr
    sys.stderr = ShutdownErrorFilter(original_stderr)

    # Install custom exception hook to suppress shutdown errors
    original_excepthook = sys.excepthook

    def custom_excepthook(exc_type, exc_value, exc_traceback) -> None:
        """Custom exception hook to suppress expected shutdown errors"""
        # Suppress CancelledError during shutdown
        if exc_type == asyncio.CancelledError:
            return
        # Suppress BrokenPipeError and ConnectionResetError during shutdown
        if exc_type in (BrokenPipeError, ConnectionResetError):
            return
        # Call original handler for other exceptions
        original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = custom_excepthook

    try:
        # Run Uvicorn server with optimized shutdown settings
        uvicorn.run(
            "main:app",
            host=config.HOST,
            port=config.PORT,
            reload=config.DEBUG,  # Auto-reload in debug mode
            log_level="info",
            log_config=None,  # Use our custom logging configuration
            timeout_graceful_shutdown=5,  # Fast shutdown for cleaner exit
            limit_concurrency=1000,  # Prevent too many hanging connections
            timeout_keep_alive=5  # Close idle connections faster
        )
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        logger.info("=" * 80)
        logger.info("Shutting down gracefully...")
        logger.info("=" * 80)
    finally:
        # Restore original stderr and exception hook
        sys.stderr = original_stderr
        sys.excepthook = original_excepthook
