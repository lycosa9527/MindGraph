import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from services.infrastructure.spa_handler import VUE_DIST_DIR

"""
Vue SPA Router
==============

FastAPI router for serving Vue 3 SPA in production mode.
This router is conditionally included when Vue SPA is available.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
"""



logger = logging.getLogger(__name__)

router = APIRouter(tags=["Vue SPA"])


@router.get("/favicon.svg")
async def vue_favicon():
    """Serve favicon from Vue dist."""
    favicon_path = VUE_DIST_DIR / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(
            path=str(favicon_path),
            media_type="image/svg+xml"
        )
    # Fallback to public folder (dev mode)
    fallback_path = VUE_DIST_DIR.parent / "public" / "favicon.svg"
    if fallback_path.exists():
        return FileResponse(
            path=str(fallback_path),
            media_type="image/svg+xml"
        )
    raise HTTPException(status_code=404, detail="Favicon not found")


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


@router.get("/pub-dash", response_class=HTMLResponse)
async def vue_pub_dash(request: Request):
    """Serve Vue SPA for public dashboard route."""
    return await _serve_index()


@router.get("/debug", response_class=HTMLResponse)
async def vue_debug(request: Request):
    """Serve Vue SPA for debug route."""
    return await _serve_index()


@router.get("/mindmate", response_class=HTMLResponse)
async def vue_mindmate(request: Request):
    """Serve Vue SPA for mindmate route."""
    return await _serve_index()


@router.get("/mindgraph", response_class=HTMLResponse)
async def vue_mindgraph(request: Request):
    """Serve Vue SPA for mindgraph route."""
    return await _serve_index()


@router.get("/canvas", response_class=HTMLResponse)
async def vue_canvas(request: Request):
    """Serve Vue SPA for canvas route."""
    return await _serve_index()


@router.get("/template", response_class=HTMLResponse)
async def vue_template(request: Request):
    """Serve Vue SPA for template route."""
    return await _serve_index()


@router.get("/course", response_class=HTMLResponse)
async def vue_course(request: Request):
    """Serve Vue SPA for course route."""
    return await _serve_index()


@router.get("/community", response_class=HTMLResponse)
async def vue_community(request: Request):
    """Serve Vue SPA for community route."""
    return await _serve_index()


@router.get("/school-zone", response_class=HTMLResponse)
async def vue_school_zone(request: Request):
    """Serve Vue SPA for school-zone route."""
    return await _serve_index()


@router.get("/school-zone/{path:path}", response_class=HTMLResponse)
async def vue_school_zone_sub(request: Request, path: str):
    """Serve Vue SPA for school-zone sub-routes."""
    return await _serve_index()


@router.get("/knowledge-space", response_class=HTMLResponse)
async def vue_knowledge_space(request: Request):
    """Serve Vue SPA for knowledge-space route."""
    return await _serve_index()


@router.get("/knowledge-space/{path:path}", response_class=HTMLResponse)
async def vue_knowledge_space_sub(request: Request, path: str):
    """Serve Vue SPA for knowledge-space sub-routes."""
    return await _serve_index()


@router.get("/askonce", response_class=HTMLResponse)
async def vue_askonce(request: Request):
    """Serve Vue SPA for askonce route."""
    return await _serve_index()


@router.get("/debateverse", response_class=HTMLResponse)
async def vue_debateverse(request: Request):
    """Serve Vue SPA for debateverse route."""
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
