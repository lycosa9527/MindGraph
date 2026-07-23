"""Vue SPA Router.

FastAPI router for serving Vue 3 SPA in production mode.
This router is conditionally included when Vue SPA is available.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from services.infrastructure.utils.pwa_manifest import (
    build_pwa_manifest,
    public_site_origin_from_request,
)
from services.infrastructure.utils.spa_handler import (
    CSP_NONCE_STATE_ATTR,
    VUE_DIST_DIR,
    apply_no_cache_headers,
    ensure_csp_meta_cos_hosts,
    generate_csp_nonce,
    inject_csp_nonce,
    media_type_for_vue_dist_relpath,
)
from services.showcase.storage import cos_showcase_enabled
from services.utils.tencent_cos_client import cos_browser_csp_sources
from utils.privacy_policy_static import privacy_policy_source_path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Vue SPA"])

_PUBLIC_DASHBOARD_ADMIN = "/admin?tab=settings&subtab=public_dashboard"


@router.get("/_diagnostic/static-files")
async def diagnostic_static_files():
    """Diagnostic endpoint to check static file serving configuration."""
    index_path = VUE_DIST_DIR / "index.html"
    assets_dir = VUE_DIST_DIR / "assets"
    asset_count = 0
    if assets_dir.is_dir():
        asset_count = sum(1 for _ in assets_dir.iterdir())

    return {
        "vue_dist_dir": str(VUE_DIST_DIR),
        "vue_dist_dir_exists": VUE_DIST_DIR.exists(),
        "vue_dist_dir_absolute": str(VUE_DIST_DIR.resolve()),
        "index_html_exists": index_path.exists(),
        "assets_dir_exists": assets_dir.is_dir(),
        "assets_file_count": asset_count,
        "current_working_directory": os.getcwd(),
    }


@router.get("/favicon.svg")
async def vue_favicon():
    """Serve favicon from Vue dist."""
    favicon_path = VUE_DIST_DIR / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(path=str(favicon_path), media_type="image/svg+xml")
    # Fallback to public folder (dev mode)
    fallback_path = VUE_DIST_DIR.parent / "public" / "favicon.svg"
    if fallback_path.exists():
        return FileResponse(path=str(fallback_path), media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")


@router.get("/", response_class=HTMLResponse)
async def vue_index(request: Request):
    """Serve Vue SPA index for root path."""
    return await _serve_index(request)


@router.get("/editor", response_class=HTMLResponse)
async def vue_editor(request: Request):
    """Serve Vue SPA for editor route."""
    return await _serve_index(request)


@router.get("/admin", response_class=HTMLResponse)
async def vue_admin(request: Request):
    """Serve Vue SPA for admin route."""
    return await _serve_index(request)


@router.get("/admin/{path:path}", response_class=HTMLResponse)
async def vue_admin_sub(request: Request, path: str):
    """Serve Vue SPA for admin sub-routes."""
    _ = path  # Path parameter required by FastAPI but not used
    return await _serve_index(request)


@router.get("/login", response_class=HTMLResponse)
async def vue_login(request: Request):
    """Serve Vue SPA for login route."""
    return await _serve_index(request)


@router.get("/auth", response_class=HTMLResponse)
async def vue_auth(request: Request):
    """Serve Vue SPA for auth route."""
    return await _serve_index(request)


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy_static():
    """Serve crawlable static privacy policy (Chrome Web Store, no JS required)."""
    policy_path = privacy_policy_source_path()
    if not policy_path.is_file():
        raise HTTPException(status_code=503, detail="Privacy policy page not generated")
    response = FileResponse(path=str(policy_path), media_type="text/html")
    apply_no_cache_headers(response)
    return response


@router.get("/bayi/passkey", response_class=HTMLResponse)
async def vue_bayi_passkey(request: Request):
    """Serve Vue SPA for Bayi passkey login route."""
    return await _serve_index(request)


@router.get("/demo", response_class=HTMLResponse)
async def vue_demo_redirect():
    """Legacy URL: send users to Bayi passkey page."""
    return RedirectResponse(url="/bayi/passkey", status_code=301)


@router.get("/dashboard", response_class=HTMLResponse)
async def vue_dashboard(_request: Request):
    """Legacy URL — national data center lives in the admin panel."""
    return RedirectResponse(url=_PUBLIC_DASHBOARD_ADMIN, status_code=301)


@router.get("/dashboard/login", response_class=HTMLResponse)
async def vue_dashboard_login(_request: Request):
    """Legacy passkey login URL — redirect to the admin national data center."""
    return RedirectResponse(url=_PUBLIC_DASHBOARD_ADMIN, status_code=301)


@router.get("/pub-dash", response_class=HTMLResponse)
async def vue_pub_dash(_request: Request):
    """Legacy public dashboard URL — redirect to the admin national data center."""
    return RedirectResponse(url=_PUBLIC_DASHBOARD_ADMIN, status_code=301)


@router.get("/debug", response_class=HTMLResponse)
async def vue_debug(request: Request):
    """Serve Vue SPA for debug route."""
    return await _serve_index(request)


@router.get("/mindmate", response_class=HTMLResponse)
async def vue_mindmate(request: Request):
    """Serve Vue SPA for mindmate route."""
    return await _serve_index(request)


@router.get("/mindgraph", response_class=HTMLResponse)
async def vue_mindgraph(request: Request):
    """Serve Vue SPA for mindgraph route."""
    return await _serve_index(request)


@router.get("/canvas", response_class=HTMLResponse)
async def vue_canvas(request: Request):
    """Serve Vue SPA for canvas route."""
    return await _serve_index(request)


@router.get("/export-render", response_class=HTMLResponse)
async def vue_export_render(request: Request):
    """Serve Vue SPA for headless export-render route (Playwright screenshot)."""
    return await _serve_index(request)


@router.get("/template", response_class=HTMLResponse)
async def vue_template(request: Request):
    """Serve Vue SPA for template route."""
    return await _serve_index(request)


@router.get("/course", response_class=HTMLResponse)
async def vue_course(request: Request):
    """Serve Vue SPA for course route."""
    return await _serve_index(request)


@router.get("/community", response_class=HTMLResponse)
async def vue_community(request: Request):
    """Serve Vue SPA for community route."""
    return await _serve_index(request)


@router.get("/showcase", response_class=HTMLResponse)
async def vue_showcase(request: Request):
    """Serve Vue SPA for showcase route."""
    return await _serve_index(request)


@router.get("/showcase/{path:path}", response_class=HTMLResponse)
async def vue_showcase_sub(request: Request, path: str):
    """Serve Vue SPA for showcase sub-routes."""
    _ = path  # Path parameter required by FastAPI but not used
    return await _serve_index(request)


@router.get("/knowledge-space", response_class=HTMLResponse)
async def vue_knowledge_space(request: Request):
    """Serve Vue SPA for knowledge-space route."""
    return await _serve_index(request)


@router.get("/knowledge-space/{path:path}", response_class=HTMLResponse)
async def vue_knowledge_space_sub(request: Request, path: str):
    """Serve Vue SPA for knowledge-space sub-routes."""
    _ = path  # Path parameter required by FastAPI but not used
    return await _serve_index(request)


@router.get("/askonce", response_class=HTMLResponse)
async def vue_askonce(request: Request):
    """Serve Vue SPA for askonce route."""
    return await _serve_index(request)


@router.get("/debateverse", response_class=HTMLResponse)
async def vue_debateverse(request: Request):
    """Serve Vue SPA for debateverse route."""
    return await _serve_index(request)


@router.get("/manifest.webmanifest")
async def vue_pwa_manifest(request: Request):
    """Serve PWA manifest with absolute URLs tied to the public site origin."""
    origin = public_site_origin_from_request(request)
    return JSONResponse(
        build_pwa_manifest(origin),
        media_type="application/manifest+json",
    )


@router.get("/index.html", response_class=HTMLResponse)
async def vue_index_html(request: Request):
    """Serve SPA shell for Workbox navigateFallback and direct /index.html requests."""
    return await _serve_index(request)


@router.get("/{path:path}")
async def vue_catch_all(request: Request, path: str):
    """Catch-all route for Vue SPA client-side routing.

    This handles any route that isn't matched by API endpoints or static files.
    First checks if the path is a static file in dist root, then falls back to SPA routing.
    Vue Router will handle the actual routing client-side.
    """
    # Skip API routes, static files, and other non-SPA routes.
    # Keep exclusions aligned with _NON_SPA_PREFIXES in spa_handler.py (cache-control).
    if (
        path.startswith("api/")
        or path.startswith("static/")
        or path.startswith("assets/")
        or path.startswith("gallery/")
        or path.startswith("thinking_mode/")
        or path.startswith("ws")
        or path in ["health", "healthz", "ready", "docs", "redoc", "openapi.json"]
    ):
        raise HTTPException(status_code=404, detail="Not found")

    # Check if this is a file with extension - try to serve from dist root first
    if "." in path.split("/")[-1]:
        file_path = VUE_DIST_DIR / path
        logger.info("[Catch-all] Checking file: %s (exists: %s)", file_path, file_path.exists())
        if file_path.exists() and file_path.is_file():
            media_type = media_type_for_vue_dist_relpath(path)
            logger.info("[Catch-all] Serving file: %s", file_path)
            return FileResponse(path=str(file_path), media_type=media_type)
        # File doesn't exist, return 404
        logger.warning("[Catch-all] File not found: %s (VUE_DIST_DIR: %s)", file_path, VUE_DIST_DIR)
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    # No file extension - this is an SPA route, serve index.html
    return await _serve_index(request)


def _frontend_not_built_response() -> HTMLResponse:
    """Return the 503 shell shown when the Vue build is missing."""
    index_path = VUE_DIST_DIR / "index.html"
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
        status_code=503,
    )


async def _serve_index(request: Request) -> HTMLResponse:
    """Serve the Vue SPA shell with a per-request CSP nonce.

    The shell HTML is read fresh, stamped with a single-use nonce on its inline
    scripts and in-document CSP meta tag, and returned as ``no-store`` so the
    nonce never goes stale against the matching ``Content-Security-Policy`` header
    emitted by ``add_security_headers``.
    """
    index_path = VUE_DIST_DIR / "index.html"
    logger.debug("Serving Vue SPA index - checking path: %s", index_path)

    if not index_path.exists():
        return _frontend_not_built_response()

    logger.info("Serving Vue SPA index.html from: %s", index_path)
    nonce = generate_csp_nonce()
    setattr(request.state, CSP_NONCE_STATE_ATTR, nonce)
    html = inject_csp_nonce(index_path.read_text(encoding="utf-8"), nonce)
    # Header ∩ meta: stamp COS hosts into meta so old dist shells still allow
    # Showcase browser→COS PUT after a backend-only CSP fix.
    if cos_showcase_enabled():
        html = ensure_csp_meta_cos_hosts(html, cos_browser_csp_sources())

    response = HTMLResponse(content=html)
    apply_no_cache_headers(response)
    return response
