"""Vue SPA Handler.

Handles serving the Vue 3 SPA in production mode.
In development, the Vite dev server handles frontend routing.

Usage:
    - Production: Build Vue app with `npm run build`, then serve from /frontend/dist
    - Development: Run Vite dev server (e.g., `npm run dev`), backend will skip SPA serving

Environment Variables:
    - SPA_MODE: 'vue' (force Vue SPA), 'legacy' (disable Vue SPA), 'auto' (default, auto-detect)
    - DEBUG=True: Automatically disables Vue SPA serving in auto mode
    - ENVIRONMENT=development: Automatically disables Vue SPA serving in auto mode
    - VITE_DEV_PORT: Automatically disables Vue SPA serving in auto mode

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import mimetypes
import os
import re
import secrets
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

# Vue SPA dist directory
# Path: services/infrastructure/utils/spa_handler.py -> go up 4 levels to project root
VUE_DIST_DIR = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"

# Per-request CSP nonce wiring (see add_security_headers + _serve_index).
# Stored on request.state so the security-headers middleware can emit a matching
# ``script-src 'self' 'nonce-<value>'`` header for the same response that carries
# the nonce-stamped HTML shell.
CSP_NONCE_STATE_ATTR = "csp_nonce"

# Opening <script ...> tags (inline or external). [^>]* never crosses '>', which is
# safe for the script tags Vite emits (no '>' inside their attribute values).
_SCRIPT_OPEN_RE = re.compile(r"<script\b([^>]*)>", re.IGNORECASE)
_SCRIPT_HAS_NONCE_RE = re.compile(r"\bnonce\s*=", re.IGNORECASE)

# Vite emits a document CSP <meta> for local dev (no FastAPI header). In
# production FastAPI serves the shell with a full Content-Security-Policy
# header (nonce + COS hosts). Dual policies are intersected by browsers, so the
# meta tag is stripped on serve — the HTTP header is the sole document policy.
_DOCUMENT_CSP_META_RE = re.compile(
    r"<meta\b[^>]*\bhttp-equiv\s*=\s*['\"]Content-Security-Policy['\"][^>]*>\s*",
    re.IGNORECASE | re.DOTALL,
)


def generate_csp_nonce() -> str:
    """Return a fresh, URL-safe CSP nonce for a single response."""
    return secrets.token_urlsafe(16)


def strip_document_csp_meta(html: str) -> str:
    """Remove the in-document CSP meta so only the HTTP header policy applies."""
    return _DOCUMENT_CSP_META_RE.sub("", html, count=1)


def inject_csp_nonce(html: str, nonce: str) -> str:
    """Stamp ``nonce`` onto ``<script>`` tags for the matching HTTP CSP header.

    External (``src``) scripts stay allowed by ``'self'``; the nonce on them is
    harmless. Inline scripts require the nonce so injected (XSS) scripts are blocked.
    Document CSP ``<meta>`` is removed separately via ``strip_document_csp_meta``.
    """

    def _add_nonce(match: re.Match[str]) -> str:
        attrs = match.group(1)
        if _SCRIPT_HAS_NONCE_RE.search(attrs):
            return match.group(0)
        return f'<script nonce="{nonce}"{attrs}>'

    return _SCRIPT_OPEN_RE.sub(_add_nonce, html)


def media_type_for_vue_dist_relpath(relpath: str) -> str:
    """Return Content-Type for a file under frontend/dist (catch-all static serving)."""
    guessed, _encoding = mimetypes.guess_type(relpath, strict=False)
    return guessed or "application/octet-stream"


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


def is_dev_mode() -> bool:
    """Check if we're running in development mode."""
    return (
        os.getenv("VITE_DEV_PORT") is not None
        or os.getenv("DEBUG", "").lower() == "true"
        or os.getenv("ENVIRONMENT", "").lower() == "development"
    )


def should_serve_vue_spa() -> bool:
    """
    Determine if we should serve Vue SPA based on mode and availability.

    In development mode (when VITE_DEV_PORT is set or DEBUG=True),
    we skip serving the built SPA to allow Vite dev server to handle it.
    """
    mode = get_spa_env_mode()

    if is_dev_mode() and mode == "auto":
        logger.info("Development mode detected. Skipping Vue SPA serving (Vite dev server will handle frontend).")
        return False

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


def setup_static_files(app: FastAPI) -> None:
    """
    Mount /static for backend-generated content (community thumbnails, etc.).

    Must run in both dev and production so community thumbnails and other
    runtime uploads are always served. In dev, Vite proxies /static to backend.
    """
    static_dir = Path(__file__).parent.parent.parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.debug("Mounted /static for runtime uploads (community, announcements, etc.)")
    else:
        logger.warning(
            "Static directory not found at %s - community thumbnails will 404",
            static_dir,
        )


def setup_vue_spa(app: FastAPI) -> bool:
    """
    Setup Vue SPA serving for production.

    Args:
        app: FastAPI application instance

    Returns:
        True if Vue SPA was configured, False if not serving SPA
    """
    # Always mount /static - needed for community thumbnails in dev and prod
    setup_static_files(app)

    if not should_serve_vue_spa():
        # Don't log misleading message in dev mode - Vite handles frontend, not legacy templates
        if not is_dev_mode():
            logger.info("Using legacy Jinja2 templates for frontend")
        return False

    logger.info("Configuring Vue SPA from: %s", VUE_DIST_DIR)

    # Mount Vue static assets (must match script/link tags in dist/index.html)
    assets_dir = VUE_DIST_DIR / "assets"
    if not assets_dir.is_dir():
        logger.critical(
            "Vue SPA enabled but %s is missing — /assets/* will 404 as JSON; "
            "deploy the full frontend build (entire frontend/dist, including assets/).",
            assets_dir,
        )
    else:
        asset_files = list(assets_dir.iterdir())
        if not asset_files:
            logger.critical(
                "Vue SPA enabled but %s is empty — redeploy after `npm run build`.",
                assets_dir,
            )
        else:
            logger.info("Mounted /assets with %s files from %s", len(asset_files), assets_dir)
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="vue-assets")

    # Mount gallery folder for featured diagrams
    gallery_dir = VUE_DIST_DIR / "gallery"
    if gallery_dir.exists():
        app.mount("/gallery", StaticFiles(directory=str(gallery_dir)), name="vue-gallery")
        logger.debug("Mounted /gallery for featured diagrams")

    return True


async def serve_vue_spa() -> FileResponse | HTMLResponse:
    """
    Serve Vue SPA index.html for client-side routing.

    This handler returns index.html for all non-API routes,
    allowing Vue Router to handle the routing client-side.
    """
    index_path = VUE_DIST_DIR / "index.html"

    if not index_path.exists():
        logger.error("Vue SPA index.html not found at %s", index_path)
        return HTMLResponse(
            content="<h1>Frontend not built</h1><p>Run 'npm run build' in the frontend directory.</p>",
            status_code=503,
        )

    return FileResponse(path=str(index_path), media_type="text/html")


# Prefixes never handled by Vue Router (aligned with vue_spa catch-all + static mounts).
_NON_SPA_PREFIXES = (
    "/api",
    "/static",
    "/assets",
    "/gallery",
    "/ws",
    "/thinking_mode",
)

_NON_SPA_EXACT_PATHS = frozenset(
    {
        "/health",
        "/healthz",
        "/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/privacy",
    }
)

# PWA / deploy-sensitive dist root files (extension-bearing; not SPA routes).
_PWA_NO_CACHE_EXACT_PATHS = frozenset(
    {
        "/manifest.webmanifest",
        "/sw.js",
    }
)

# Hashed bundles, runtime uploads, and PWA icons — no session/auth middleware.
_PUBLIC_STATIC_PREFIXES = (
    "/assets/",
    "/static/",
    "/gallery/",
)

_PUBLIC_STATIC_EXACT_PATHS = frozenset(
    {
        "/favicon.ico",
        "/favicon.svg",
        "/robots.txt",
        "/apple-touch-icon.png",
        "/pwa-192x192.png",
        "/pwa-512x512.png",
    }
)


def _path_last_segment(path: str) -> str:
    """Path last segment."""
    trimmed = path.rstrip("/")
    if not trimmed:
        return ""
    return trimmed.split("/")[-1]


def _has_file_extension(path: str) -> bool:
    """Has file extension."""
    return "." in _path_last_segment(path)


def is_pwa_no_cache_path(path: str) -> bool:
    """True for service worker and dynamic manifest paths that must revalidate after deploy."""
    if path in _PWA_NO_CACHE_EXACT_PATHS:
        return True
    basename = _path_last_segment(path)
    if basename.startswith("workbox-") and (basename.endswith(".js") or basename.endswith(".mjs")):
        return True
    return False


def is_public_static_path(path: str) -> bool:
    """
    True for immutable or public static responses that must not run session/auth middleware.

    Covers Vue ``/assets/*``, runtime ``/static/*``, gallery images, PWA bootstrap files,
    health probes, and root icons. Aligned with abuseipdb static skip paths.
    """
    if any(path.startswith(prefix) for prefix in _PUBLIC_STATIC_PREFIXES):
        return True
    if path in _PUBLIC_STATIC_EXACT_PATHS:
        return True
    if is_pwa_no_cache_path(path):
        return True
    if path.startswith("/health"):
        return True
    return False


def is_spa_route(path: str) -> bool:
    """
    True when the path is a Vue client route (production serves index.html).

    Matches vue_spa catch-all: extensionless paths that are not API/static mounts.
    """
    if any(path.startswith(prefix) for prefix in _NON_SPA_PREFIXES):
        return False
    if path in _NON_SPA_EXACT_PATHS:
        return False
    if _has_file_extension(path):
        return False
    return True


def should_apply_no_cache(path: str, content_type: str | None = None) -> bool:
    """
    Whether to attach no-store cache headers to this response.

    Covers SPA shell routes, HTML files, PWA bootstrap assets, and text/html
    responses (safety net when index.html is served on an unexpected path).
    """
    if is_pwa_no_cache_path(path):
        return True
    if path.endswith(".html"):
        return True
    if is_spa_route(path):
        return True
    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    return normalized_type == "text/html"


def apply_no_cache_headers(response) -> None:
    """Set standard no-store headers on a Starlette/FastAPI response."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


def should_apply_api_no_cache(path: str, response) -> bool:
    """
    Default API responses to no-cache unless the handler already set Cache-Control.

    Preserves intentional caching on endpoints such as image proxy or PNG export.
    """
    if not path.startswith("/api/"):
        return False
    if response.headers.get("cache-control"):
        return False
    return True
