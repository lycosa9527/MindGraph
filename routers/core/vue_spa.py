"""Vue SPA Router.

FastAPI router for serving Vue 3 SPA in production mode.
This router is conditionally included when Vue SPA is available.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved.
"""

import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from services.infrastructure.utils.spa_handler import VUE_DIST_DIR


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Vue SPA"])


@router.get("/_diagnostic/static-files")
async def diagnostic_static_files():
    """Diagnostic endpoint to check static file serving configuration."""
    index_path = VUE_DIST_DIR / "index.html"

    return {
        "vue_dist_dir": str(VUE_DIST_DIR),
        "vue_dist_dir_exists": VUE_DIST_DIR.exists(),
        "vue_dist_dir_absolute": str(VUE_DIST_DIR.resolve()),
        "index_html_exists": index_path.exists(),
        "current_working_directory": os.getcwd(),
    }


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
async def vue_index():
    """Serve Vue SPA index for root path."""
    return await _serve_index()


@router.get("/editor", response_class=HTMLResponse)
async def vue_editor():
    """Serve Vue SPA for editor route."""
    return await _serve_index()


@router.get("/admin", response_class=HTMLResponse)
async def vue_admin():
    """Serve Vue SPA for admin route."""
    return await _serve_index()


@router.get("/admin/{path:path}", response_class=HTMLResponse)
async def vue_admin_sub(path: str):
    """Serve Vue SPA for admin sub-routes."""
    _ = path  # Path parameter required by FastAPI but not used
    return await _serve_index()


@router.get("/login", response_class=HTMLResponse)
async def vue_login():
    """Serve Vue SPA for login route."""
    return await _serve_index()


@router.get("/auth", response_class=HTMLResponse)
async def vue_auth():
    """Serve Vue SPA for auth route."""
    return await _serve_index()


@router.get("/demo", response_class=HTMLResponse)
async def vue_demo():
    """Serve Vue SPA for demo route."""
    return await _serve_index()


@router.get("/dashboard", response_class=HTMLResponse)
async def vue_dashboard():
    """Serve Vue SPA for dashboard route."""
    return await _serve_index()


@router.get("/dashboard/login", response_class=HTMLResponse)
async def vue_dashboard_login():
    """Serve Vue SPA for dashboard login route."""
    return await _serve_index()


@router.get("/pub-dash", response_class=HTMLResponse)
async def vue_pub_dash():
    """Serve Vue SPA for public dashboard route."""
    return await _serve_index()


@router.get("/debug", response_class=HTMLResponse)
async def vue_debug():
    """Serve Vue SPA for debug route."""
    return await _serve_index()


@router.get("/mindmate", response_class=HTMLResponse)
async def vue_mindmate():
    """Serve Vue SPA for mindmate route."""
    return await _serve_index()


@router.get("/mindgraph", response_class=HTMLResponse)
async def vue_mindgraph():
    """Serve Vue SPA for mindgraph route."""
    return await _serve_index()


@router.get("/canvas", response_class=HTMLResponse)
async def vue_canvas():
    """Serve Vue SPA for canvas route."""
    return await _serve_index()


@router.get("/template", response_class=HTMLResponse)
async def vue_template():
    """Serve Vue SPA for template route."""
    return await _serve_index()


@router.get("/course", response_class=HTMLResponse)
async def vue_course():
    """Serve Vue SPA for course route."""
    return await _serve_index()


@router.get("/community", response_class=HTMLResponse)
async def vue_community():
    """Serve Vue SPA for community route."""
    return await _serve_index()


@router.get("/school-zone", response_class=HTMLResponse)
async def vue_school_zone():
    """Serve Vue SPA for school-zone route."""
    return await _serve_index()


@router.get("/school-zone/{path:path}", response_class=HTMLResponse)
async def vue_school_zone_sub(path: str):
    """Serve Vue SPA for school-zone sub-routes."""
    _ = path  # Path parameter required by FastAPI but not used
    return await _serve_index()


@router.get("/knowledge-space", response_class=HTMLResponse)
async def vue_knowledge_space():
    """Serve Vue SPA for knowledge-space route."""
    return await _serve_index()


@router.get("/knowledge-space/{path:path}", response_class=HTMLResponse)
async def vue_knowledge_space_sub(path: str):
    """Serve Vue SPA for knowledge-space sub-routes."""
    _ = path  # Path parameter required by FastAPI but not used
    return await _serve_index()


@router.get("/askonce", response_class=HTMLResponse)
async def vue_askonce():
    """Serve Vue SPA for askonce route."""
    return await _serve_index()


@router.get("/debateverse", response_class=HTMLResponse)
async def vue_debateverse():
    """Serve Vue SPA for debateverse route."""
    return await _serve_index()


@router.get("/{path:path}")
async def vue_catch_all(path: str):
    """Catch-all route for Vue SPA client-side routing.

    This handles any route that isn't matched by API endpoints or static files.
    First checks if the path is a static file in dist root, then falls back to SPA routing.
    Vue Router will handle the actual routing client-side.
    """
    # Skip API routes, static files, and other non-SPA routes
    if (
        path.startswith("api/")
        or path.startswith("static/")
        or path.startswith("assets/")
        or path.startswith("gallery/")
        or path.startswith("ws")
        or path in ["health", "healthz", "ready", "docs", "redoc", "openapi.json"]
    ):
        raise HTTPException(status_code=404, detail="Not found")

    # Check if this is a file with extension - try to serve from dist root first
    if "." in path.split("/")[-1]:
        file_path = VUE_DIST_DIR / path
        logger.info("[Catch-all] Checking file: %s (exists: %s)", file_path, file_path.exists())
        if file_path.exists() and file_path.is_file():
            # Determine media type based on extension
            media_type = "application/octet-stream"
            if path.endswith(".js") or path.endswith(".mjs"):
                media_type = "application/javascript"
            elif path.endswith(".css"):
                media_type = "text/css"
            elif path.endswith(".svg"):
                media_type = "image/svg+xml"
            elif path.endswith(".png"):
                media_type = "image/png"
            elif path.endswith(".jpg") or path.endswith(".jpeg"):
                media_type = "image/jpeg"
            elif path.endswith(".webp"):
                media_type = "image/webp"
            elif path.endswith(".json"):
                media_type = "application/json"
            elif path.endswith(".ico"):
                media_type = "image/x-icon"

            logger.info("[Catch-all] Serving file: %s", file_path)
            return FileResponse(
                path=str(file_path),
                media_type=media_type
            )
        # File doesn't exist, return 404
        logger.warning("[Catch-all] File not found: %s (VUE_DIST_DIR: %s)", file_path, VUE_DIST_DIR)
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    # No file extension - this is an SPA route, serve index.html
    return await _serve_index()


async def _serve_index() -> FileResponse:
    """Serve Vue SPA index.html."""
    index_path = VUE_DIST_DIR / "index.html"
    logger.debug("Serving Vue SPA index - checking path: %s", index_path)
    logger.debug("VUE_DIST_DIR exists: %s", VUE_DIST_DIR.exists())
    logger.debug("index.html exists: %s", index_path.exists())

    if not index_path.exists():
        logger.error("Vue SPA index.html not found at: %s", index_path)
        logger.error("VUE_DIST_DIR: %s", VUE_DIST_DIR)
        logger.error("VUE_DIST_DIR absolute: %s", VUE_DIST_DIR.resolve())
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head><title>Frontend Not Built</title></head>
            <body>
                <h1>Frontend Not Built</h1>
                <p>The Vue frontend has not been built yet.</p>
                <p>Expected path: {index_path}</p>
                <p>VUE_DIST_DIR: {VUE_DIST_DIR}</p>
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

    logger.info("Serving Vue SPA index.html from: %s", index_path)
    return FileResponse(
        path=str(index_path),
        media_type="text/html"
    )
