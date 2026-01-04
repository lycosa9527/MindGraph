"""
Vue SPA Router
==============

FastAPI router for serving Vue 3 SPA in production mode.
This router is conditionally included when Vue SPA is available.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse

from services.spa_handler import VUE_DIST_DIR, is_vue_spa_available

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Vue SPA"])


@router.get("/", response_class=HTMLResponse)
async def vue_index(request: Request):
    """Serve Vue SPA index for root path."""
    return await _serve_index()


@router.get("/editor", response_class=HTMLResponse)
async def vue_editor(request: Request):
    """Serve Vue SPA for editor route."""
    return await _serve_index()


@router.get("/admin", response_class=HTMLResponse)
async def vue_admin(request: Request):
    """Serve Vue SPA for admin route."""
    return await _serve_index()


@router.get("/admin/{path:path}", response_class=HTMLResponse)
async def vue_admin_sub(request: Request, path: str):
    """Serve Vue SPA for admin sub-routes."""
    return await _serve_index()


@router.get("/login", response_class=HTMLResponse)
async def vue_login(request: Request):
    """Serve Vue SPA for login route."""
    return await _serve_index()


@router.get("/auth", response_class=HTMLResponse)
async def vue_auth(request: Request):
    """Serve Vue SPA for auth route."""
    return await _serve_index()


@router.get("/demo", response_class=HTMLResponse)
async def vue_demo(request: Request):
    """Serve Vue SPA for demo route."""
    return await _serve_index()


@router.get("/dashboard", response_class=HTMLResponse)
async def vue_dashboard(request: Request):
    """Serve Vue SPA for dashboard route."""
    return await _serve_index()


@router.get("/dashboard/login", response_class=HTMLResponse)
async def vue_dashboard_login(request: Request):
    """Serve Vue SPA for dashboard login route."""
    return await _serve_index()


async def _serve_index() -> FileResponse:
    """Serve Vue SPA index.html."""
    index_path = VUE_DIST_DIR / "index.html"
    
    if not index_path.exists():
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Frontend Not Built</title></head>
            <body>
                <h1>Frontend Not Built</h1>
                <p>The Vue frontend has not been built yet.</p>
                <p>Run the following commands:</p>
                <pre>
cd frontend
npm install
npm run build
                </pre>
            </body>
            </html>
            """,
            status_code=503
        )
    
    return FileResponse(
        path=str(index_path),
        media_type="text/html"
    )
