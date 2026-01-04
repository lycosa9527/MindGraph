"""
Vue SPA Handler
===============

Handles serving the Vue 3 SPA in production mode.
In development, the Vite dev server handles frontend routing.

Usage:
    - Production: Build Vue app with `npm run build`, then serve from /frontend/dist
    - Development: Run Vite dev server on port 3000, backend on port 8000

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
"""

import os
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

# Vue SPA dist directory
VUE_DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"


def is_vue_spa_available() -> bool:
    """Check if Vue SPA build is available."""
    index_html = VUE_DIST_DIR / "index.html"
    return VUE_DIST_DIR.exists() and index_html.exists()


def get_spa_env_mode() -> str:
    """
    Get SPA serving mode from environment.
    
    Returns:
        'vue' - Serve Vue SPA (production)
        'legacy' - Serve Jinja2 templates (backward compatibility)
        'auto' - Auto-detect based on Vue build availability
    """
    return os.getenv("SPA_MODE", "auto").lower()


def should_serve_vue_spa() -> bool:
    """
    Determine if we should serve Vue SPA based on mode and availability.
    """
    mode = get_spa_env_mode()
    
    if mode == "vue":
        if not is_vue_spa_available():
            logger.warning("SPA_MODE=vue but Vue build not found at frontend/dist. Falling back to legacy templates.")
            return False
        return True
    
    if mode == "legacy":
        return False
    
    # Auto mode: use Vue if available
    if mode == "auto":
        available = is_vue_spa_available()
        if available:
            logger.info("Vue SPA build detected. Serving Vue frontend.")
        return available
    
    return False


def setup_vue_spa(app: FastAPI) -> bool:
    """
    Setup Vue SPA serving for production.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        True if Vue SPA was configured, False if using legacy templates
    """
    if not should_serve_vue_spa():
        logger.info("Using legacy Jinja2 templates for frontend")
        return False
    
    logger.info(f"Configuring Vue SPA from: {VUE_DIST_DIR}")
    
    # Mount Vue static assets
    assets_dir = VUE_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="vue-assets")
    
    return True


async def serve_vue_spa(request: Request) -> FileResponse:
    """
    Serve Vue SPA index.html for client-side routing.
    
    This handler returns index.html for all non-API routes,
    allowing Vue Router to handle the routing client-side.
    """
    index_path = VUE_DIST_DIR / "index.html"
    
    if not index_path.exists():
        logger.error(f"Vue SPA index.html not found at {index_path}")
        return HTMLResponse(
            content="<h1>Frontend not built</h1><p>Run 'npm run build' in the frontend directory.</p>",
            status_code=503
        )
    
    return FileResponse(
        path=str(index_path),
        media_type="text/html"
    )


# SPA routes that should be handled by Vue Router (not API endpoints)
VUE_SPA_ROUTES = [
    "/",
    "/editor",
    "/admin",
    "/login",
    "/auth",
    "/demo",
    "/dashboard",
    "/dashboard/login",
]


def is_spa_route(path: str) -> bool:
    """
    Check if a path should be handled by Vue SPA.
    
    API routes (/api/*) and static files (/static/*) are NOT SPA routes.
    """
    # API routes
    if path.startswith("/api"):
        return False
    
    # Static files (legacy)
    if path.startswith("/static"):
        return False
    
    # Vue assets
    if path.startswith("/assets"):
        return False
    
    # WebSocket
    if path.startswith("/ws"):
        return False
    
    # Health checks
    if path in ["/health", "/healthz", "/ready"]:
        return False
    
    # OpenAPI docs
    if path in ["/docs", "/redoc", "/openapi.json"]:
        return False
    
    # Exact SPA routes
    if path in VUE_SPA_ROUTES:
        return True
    
    # Catch-all for client-side routing (paths without file extensions)
    if "." not in path.split("/")[-1]:
        return True
    
    return False
