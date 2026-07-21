"""
Middleware configuration for MindGraph application.

Handles:
- CORS configuration
- GZip compression
- Request body size limiting
- CSRF protection
- Security headers
- Cache control headers
- Request/response logging

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import os
import time
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipResponder
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from config.settings import config
from services.auth.http_auth_token import has_authorization_mgat_bearer
from services.auth.security_logger import security_log
from services.auth.vpn_geo_enforcement import maybe_enforce_vpn_cn_geo_async
from services.infrastructure.http.feature_gate import feature_flag_gate
from services.infrastructure.security.abuseipdb_middleware import abuseipdb_middleware
from services.infrastructure.utils.spa_handler import (
    apply_no_cache_headers,
    is_public_static_path,
    should_apply_api_no_cache,
    should_apply_no_cache,
)
from services.showcase.storage import cos_showcase_enabled
from utils.auth.auth_resolution import AUTH_CONTEXT_USER_ATTR, resolve_authenticated_user_optional
from utils.auth.mg_client import REQUEST_STATE_MG_CLIENT
from utils.auth.request_helpers import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    get_client_ip,
    is_https as request_is_https,
    set_csrf_cookie,
)
from utils.db.rls_context import RlsContext, reset_rls_context, set_rls_context

logger = logging.getLogger(__name__)

# Maximum request body size (5MB) - prevents DoS attacks via large payloads
MAX_REQUEST_BODY_SIZE = 5 * 1024 * 1024  # 5MB
# Showcase publish: doc + optional videos (see showcase_helpers VIDEO_MAX_BYTES)
SHOWCASE_MAX_BODY_SIZE = 105 * 1024 * 1024  # 100MB + multipart overhead


def max_request_body_size_for_path(path: str) -> int:
    """Per-route body limit; shrink Showcase when COS mode (no large multipart)."""
    showcase_paths = (
        path == "/api/showcase/posts"
        or path.startswith("/api/showcase/posts/")
        or path == "/api/auth/admin/showcase/posts/proxy"
    )
    if showcase_paths:
        if cos_showcase_enabled():
            # Metadata + init/complete JSON only — large bytes go browser→COS
            return MAX_REQUEST_BODY_SIZE
        return SHOWCASE_MAX_BODY_SIZE
    return MAX_REQUEST_BODY_SIZE


def is_https(request: Request) -> bool:
    """Check if request is over HTTPS (shared with auth cookie helpers)."""
    return request_is_https(request)


_EMBEDDABLE_SHOWCASE_SUFFIXES = (".pdf", ".doc", ".docx")
_STREAMING_STATIC_SUFFIXES = (".mp4", ".webm", ".mov", ".m4v", ".m4a")


def allows_same_origin_showcase_frame(path: str) -> bool:
    """Showcase teaching attachments may be previewed in same-origin iframes."""
    # Public static mount is blocked; assets are served via authenticated API.
    if path.startswith("/api/showcase/assets/"):
        lower = path.lower()
        return lower.endswith(_EMBEDDABLE_SHOWCASE_SUFFIXES)
    if not (path.startswith("/static/case_square/") or path.startswith("/static/showcase/")):
        return False
    lower = path.lower()
    return lower.endswith(_EMBEDDABLE_SHOWCASE_SUFFIXES)


async def block_chat_static_uploads(request: Request, call_next):
    """
    Block direct HTTP access to workshop chat uploads on disk.

    Chat attachments must be fetched via authenticated
    ``/api/chat/attachments/{id}/download`` instead of world-readable
    ``/static/chat/`` URLs.
    """
    if request.url.path.startswith("/static/chat/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return await call_next(request)


async def block_showcase_static_uploads(request: Request, call_next):
    """
    Block direct HTTP access to Showcase files on disk.

    Pending and approved assets must be fetched via authenticated
    ``/api/showcase/assets/...`` so non-approved posts are not world-readable.
    """
    static_path = request.url.path
    if static_path.startswith("/static/case_square/") or static_path.startswith("/static/showcase/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return await call_next(request)


async def limit_request_body_size(request: Request, call_next):
    """
    Limit request body size to prevent DoS attacks.

    Rejects requests with Content-Length exceeding MAX_REQUEST_BODY_SIZE.
    This protects against attackers trying to exhaust server memory/disk
    by sending extremely large payloads (e.g., 100MB diagram specs).

    Note: This checks Content-Length header, which can be spoofed.
    For complete protection, also limit at reverse proxy level (Nginx).
    """
    content_length = request.headers.get("content-length")
    max_size = max_request_body_size_for_path(request.url.path)
    if content_length:
        try:
            size = int(content_length)
            if size > max_size:
                client_ip = request.client.host if request.client else "unknown"
                security_log.input_validation_failed(
                    field="request_body",
                    reason=(f"size {size / 1024 / 1024:.1f}MB exceeds {max_size / 1024 / 1024:.0f}MB limit"),
                    ip=client_ip,
                    value_size=size,
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body too large. Maximum size is {max_size // 1024 // 1024}MB"},
                )
        except ValueError:
            # Invalid Content-Length header, let it pass (will fail elsewhere if malformed)
            pass

    return await call_next(request)


async def csrf_protection(request: Request, call_next):
    """
    CSRF protection middleware for state-changing operations.

    Validates:
    - Origin header for POST/PUT/DELETE/PATCH requests
    - CSRF token for authenticated requests (if token provided)

    Uses SameSite cookies (already set) + Origin validation for defense in depth.
    """
    # Only check state-changing methods
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        # Skip CSRF check for:
        # - Public endpoints (login, register, etc.)
        # - API endpoints that use API keys (different auth mechanism)
        # - Health checks
        skip_paths = [
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/bayi/passkey",
            "/api/frontend_log",
            "/api/frontend_log_batch",
            "/api/gewe/webhook",
            "/api/mindbot",
            "/api/mcp",
            "/health",
            "/health/",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)

        # Validate Origin header for cross-origin requests
        origin = request.headers.get("Origin")
        _referer = request.headers.get("Referer")  # Available for future use

        if origin:
            # Extract host from origin
            try:
                origin_host = urlparse(origin).netloc
                request_host = request.url.netloc

                # Allow same-origin requests
                if origin_host == request_host:
                    pass  # Same origin, allow
                else:
                    # Cross-origin: logged only — intentional SameSite-cookie CSRF tradeoff.
                    # Tighten with Origin allowlist or mandatory X-CSRF-Token if policy changes.
                    logger.warning(
                        "Cross-origin request detected: Origin=%s, Host=%s",
                        origin_host,
                        request_host,
                    )
                    # Don't block - SameSite cookies will prevent CSRF
            except (ValueError, AttributeError) as e:
                logger.debug("Origin validation error (non-critical): %s", e)

        # mgat_ clients (OpenClaw, Chrome extension, file-reader) authenticate via
        # Authorization header; browsers may still attach session cookies from a
        # prior web login — skip double-submit CSRF only for explicit mgat_ Bearer.
        if not has_authorization_mgat_bearer(request):
            # Require double-submit CSRF token for cookie-authenticated mutations.
            # Migration-safe: when the access_token cookie exists but no csrf_token
            # cookie has been issued yet (e.g. sessions created before this rollout),
            # allow the request once and let the response below bootstrap the cookie.
            # Strict match is enforced as soon as the csrf_token cookie is present.
            csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
            if request.cookies.get("access_token"):
                if csrf_cookie:
                    csrf_header = request.headers.get(CSRF_HEADER_NAME)
                    if not csrf_header or csrf_header != csrf_cookie:
                        logger.warning("CSRF token missing or invalid for %s", request.url.path)
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "Invalid or missing CSRF token"},
                        )
                else:
                    logger.info("CSRF bootstrap: issuing csrf_token cookie for %s", request.url.path)
                    security_log.csrf_bootstrap(request.url.path, ip=get_client_ip(request))
            elif request.headers.get(CSRF_HEADER_NAME):
                csrf_header = request.headers.get(CSRF_HEADER_NAME)
                if csrf_cookie and csrf_header != csrf_cookie:
                    logger.warning("CSRF token mismatch for %s", request.url.path)
                    return JSONResponse(status_code=403, content={"detail": "Invalid CSRF token"})

    response = await call_next(request)

    # Bootstrap the double-submit cookie for authenticated users that don't have
    # one yet (new logins are seeded in set_auth_cookies; this covers pre-existing
    # sessions and any safe-method request that arrives first).
    if request.cookies.get("access_token") and not request.cookies.get(CSRF_COOKIE_NAME):
        set_csrf_cookie(response, request)

    return response


async def add_security_headers(request: Request, call_next):
    """
    Add security headers to all HTTP responses.

    Protects against:
    - Clickjacking (X-Frame-Options)
    - MIME sniffing attacks (X-Content-Type-Options)
    - XSS attacks (X-XSS-Protection, Content-Security-Policy)
    - Information leakage (Referrer-Policy)

    CSP Policy Notes:
    - script-src: Vue SPA shell responses carry a per-request nonce (set by the SPA
      handler on request.state) so 'unsafe-inline' is dropped for the app shell.
      Legacy template responses without a nonce keep 'unsafe-inline' for their
      inline onclick handlers / config bootstrap.
    - style-src: keeps 'unsafe-inline' — Vue/Element Plus inject styles at runtime
      via JS, which a nonce cannot cover.
    - ws:/wss:: Required for Kitty Agent WebSocket connections
    - data: URIs: Required for canvas-to-image conversions
    - DEBUG mode: Allows Swagger UI CDN (cdn.jsdelivr.net) for /docs endpoint

    Reviewed: 2025-10-26 - All directives verified against actual codebase
    """
    response = await call_next(request)

    path = request.url.path
    same_origin_frame = allows_same_origin_showcase_frame(path)

    # Prevent clickjacking (stops site being embedded in iframes)
    response.headers["X-Frame-Options"] = "SAMEORIGIN" if same_origin_frame else "DENY"

    # Prevent MIME sniffing (stops browser from guessing content types)
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Note: X-XSS-Protection is intentionally omitted. The header is deprecated,
    # ignored by modern browsers, and can introduce vulnerabilities in legacy
    # ones; CSP (below) is the correct XSS control.

    # Content Security Policy (controls what resources can load)
    # Tailored specifically for MindGraph's architecture
    # In DEBUG mode, allow Swagger UI CDN for /docs and /redoc endpoints
    frame_ancestors = "'self'" if same_origin_frame else "'none'"
    if config.debug:
        # DEBUG mode: Allow Swagger UI resources from CDN (including source maps)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "worker-src 'self' blob:; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: http: https: blob: https://cdn.jsdelivr.net https://fastapi.tiangolo.com; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self' ws: wss: blob: https://cdn.jsdelivr.net; "
            "frame-src 'self' blob: https://view.officeapps.live.com; "
            f"frame-ancestors {frame_ancestors}; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
    else:
        # Production: Strict CSP without external CDN access.
        # SPA shell responses set request.state.csp_nonce, letting us drop
        # 'unsafe-inline' from script-src for the app shell. Other responses
        # (legacy templates with inline handlers) keep the permissive fallback.
        csp_nonce = getattr(request.state, "csp_nonce", None)
        script_src = f"script-src 'self' 'nonce-{csp_nonce}'; " if csp_nonce else "script-src 'self' 'unsafe-inline'; "
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"{script_src}"
            "worker-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: http: https: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss: blob:; "
            "frame-src 'self' blob: https://view.officeapps.live.com; "
            f"frame-ancestors {frame_ancestors}; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

    # Referrer Policy (controls info sent in Referer header)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Permissions Policy (restrict access to browser features)
    # Only allow microphone (for Kitty Agent), disable everything else
    response.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=(), payment=()"

    if is_https(request):
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

    return response


async def add_cache_control_headers(request: Request, call_next):
    """
    Add cache control headers for static files.

    Strategy:
    - /assets/* (content-hashed Vue bundles): cache 1 year, immutable
    - SPA shell routes, HTML, PWA bootstrap (sw.js, manifest): no-store
    - /api/* without explicit Cache-Control: no-store (SSE/image routes set their own)

    SPA path detection uses ``is_spa_route()`` in spa_handler (aligned with vue_spa
    catch-all) so new client routes do not require a manual no-cache list.
    """
    response = await call_next(request)

    path = request.url.path
    content_type = response.headers.get("content-type")

    if path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif should_apply_no_cache(path, content_type):
        apply_no_cache_headers(response)
    elif should_apply_api_no_cache(path, response):
        apply_no_cache_headers(response)
    elif path.startswith("/static/case_square/") and path.lower().endswith(".pdf"):
        apply_no_cache_headers(response)
    elif path.startswith("/api/showcase/assets/") and path.lower().endswith(".pdf"):
        apply_no_cache_headers(response)

    return response


async def enforce_streaming_body_limit(request: Request, call_next):
    """
    Enforce body size when Content-Length is absent (chunked uploads).

    Complements ``limit_request_body_size`` which only inspects Content-Length.
    Multipart is included so omitting Content-Length cannot bypass the cap.
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        content_length = request.headers.get("content-length")
        max_size = max_request_body_size_for_path(request.url.path)
        if not content_length:
            body = await request.body()
            if len(body) > max_size:
                client_ip = get_client_ip(request)
                security_log.input_validation_failed(
                    field="request_body",
                    reason=(
                        f"streamed size {len(body) / 1024 / 1024:.1f}MB exceeds {max_size / 1024 / 1024:.0f}MB limit"
                    ),
                    ip=client_ip,
                    value_size=len(body),
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": (f"Request body too large. Maximum size is {max_size // 1024 // 1024}MB")},
                )
    return await call_next(request)


class SelectiveGZipMiddleware:
    """
    GZip middleware that excludes PDF files from compression.

    PDF files must not be compressed because:
    1. They are already compressed internally
    2. Compression breaks HTTP range requests needed for lazy loading
    3. Range requests require byte-level accuracy which is lost with compression
    """

    def __init__(self, app: ASGIApp, minimum_size: int = 1000, compresslevel: int = 9):
        """init  ."""
        self.app = app
        self.minimum_size = minimum_size
        self.compresslevel = compresslevel

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """call  ."""
        if scope["type"] == "http":
            path = scope.get("path", "")
            lower_path = path.lower()
            # PDF and video responses must stay uncompressed for range requests / HTML5 media.
            is_streaming_static = lower_path.endswith(_STREAMING_STATIC_SUFFIXES)
            is_pdf_endpoint = (path.startswith("/api/library/documents/") and "/file" in path) or lower_path.endswith(
                ".pdf"
            )

            if is_pdf_endpoint or is_streaming_static:
                # Skip compression for PDF files - pass through directly
                # This preserves range request support
                await self.app(scope, receive, send)
            else:
                # Use GZipResponder for other responses (standard compression)
                responder = GZipResponder(
                    self.app,
                    minimum_size=self.minimum_size,
                    compresslevel=self.compresslevel,
                )
                await responder(scope, receive, send)
        else:
            await self.app(scope, receive, send)


async def ensure_pdf_range_support(request: Request, call_next):
    """
    Ensure PDF responses have proper headers for range request support.

    This runs after the response is created to add Accept-Ranges header
    if it's missing. This is a safety net in case SelectiveGZipMiddleware
    doesn't catch all cases.
    """
    response = await call_next(request)

    # Check if this is a PDF file response
    content_type = response.headers.get("Content-Type", "")
    path = request.url.path

    if content_type == "application/pdf" or (path.startswith("/api/library/documents/") and "/file" in path):
        # Ensure Accept-Ranges is set for range request support
        if "Accept-Ranges" not in response.headers:
            response.headers["Accept-Ranges"] = "bytes"
        # Ensure Content-Encoding is not set (shouldn't be, but double-check)
        if "Content-Encoding" in response.headers:
            encoding = response.headers["Content-Encoding"]
            if encoding in ("gzip", "deflate", "br"):
                logger.warning(
                    "[Middleware] PDF file was compressed (%s), removing compression header. "
                    "This breaks range requests! Path: %s",
                    encoding,
                    path,
                )
                del response.headers["Content-Encoding"]

    return response


async def auth_context_middleware(request: Request, call_next):
    """
    Resolve JWT/mgat_ User once per request so geo middleware and Depends() reuse it.

    Public static paths (``/assets/*``, ``/static/*``, PWA icons, etc.) skip session
    validation — browsers send auth cookies on same-origin asset requests, which would
    otherwise trigger hundreds of redundant Redis session checks on cold loads.
    """
    if request.method == "OPTIONS":
        return await call_next(request)
    if is_public_static_path(request.url.path):
        token = set_rls_context(RlsContext.deny_default())
        try:
            return await call_next(request)
        finally:
            reset_rls_context(token)
    user = await resolve_authenticated_user_optional(request)
    if user is not None:
        setattr(request.state, AUTH_CONTEXT_USER_ATTR, user)
    preset = getattr(request.state, "rls_context", None)
    if preset is not None:
        token = set_rls_context(preset)
    elif user is not None:
        token = set_rls_context(RlsContext.from_user(user))
    else:
        token = set_rls_context(RlsContext.deny_default())
    try:
        return await call_next(request)
    finally:
        reset_rls_context(token)


async def vpn_cn_geo_middleware(request: Request, call_next):
    """
    Block non-mainland-phone users when JWT country baseline (at login) was non-CN
    and the client later resolves to CN (VPN / travel), after Redis fast path.
    """
    if request.method == "OPTIONS":
        return await call_next(request)
    blocked = await maybe_enforce_vpn_cn_geo_async(request)
    if blocked is not None:
        return blocked
    return await call_next(request)


async def log_requests(request: Request, call_next):
    """
    Log all HTTP requests and responses with timing information.
    Handles request/response lifecycle events.
    """
    start_time = time.time()

    # For Vue assets, include version info in log for debugging
    log_path = request.url.path
    if request.url.path.startswith("/assets/") and request.url.query:
        log_path = f"{request.url.path}?{request.url.query}"

    # For POST requests to generate_graph, check if it's autocomplete before processing
    # This allows us to set appropriate slow warning thresholds
    is_autocomplete_request = False
    if request.method == "POST" and "generate_graph" in request.url.path:
        try:
            body = await request.body()
            if body:
                body_data = json.loads(body)
                is_autocomplete_request = body_data.get("request_type") == "autocomplete"

                # Recreate request body stream for downstream consumption
                async def _receive_body():
                    return {"type": "http.request", "body": body, "more_body": False}

                request = Request(request.scope, receive=_receive_body)
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass

    # Process request
    response = await call_next(request)

    # Log combined request/response to save space (skip noisy immutable asset traffic)
    response_time = time.time() - start_time
    if not is_public_static_path(request.url.path):
        mg_client = getattr(request.state, REQUEST_STATE_MG_CLIENT, None)
        if isinstance(mg_client, str) and mg_client:
            logger.debug(
                "Request: %s %s from %s client=%s Response: %s in %.3fs",
                request.method,
                log_path,
                get_client_ip(request),
                mg_client,
                response.status_code,
                response_time,
            )
        else:
            logger.debug(
                "Request: %s %s from %s Response: %s in %.3fs",
                request.method,
                log_path,
                get_client_ip(request),
                response.status_code,
                response_time,
            )

    # Monitor slow requests (thresholds based on endpoint type)
    if "generate_png" in request.url.path and response_time > 20:
        logger.warning(
            "Slow PNG generation: %s %s took %.3fs",
            request.method,
            request.url.path,
            response_time,
        )
    elif "generate_graph" in request.url.path:
        if is_autocomplete_request:
            # Auto-complete: Each LLM call takes 3-5s, total ~10-12s for 3-4 models
            # Based on actual performance data from CHANGELOG: first result ~3s, total ~10-12s
            # Warn if individual LLM call exceeds 8s (should be 3-5s normally)
            if response_time > 8:
                logger.warning(
                    "Slow auto-complete generation: %s %s took %.3fs "
                    "(expected 3-5s per LLM, total ~10-12s for all models)",
                    request.method,
                    request.url.path,
                    response_time,
                )
        else:
            # Initial generation: Should be fast, 2-8s typical
            # Based on actual performance: Qwen typically 2-5s, other models 3-8s
            if response_time > 5:
                logger.warning(
                    "Slow graph generation: %s %s took %.3fs (expected 2-8s)",
                    request.method,
                    request.url.path,
                    response_time,
                )
    elif "node_palette" in request.url.path and response_time > 10:
        # Node Palette streams from 4 LLMs, 5-8s is normal
        logger.warning(
            "Slow node palette: %s %s took %.3fs",
            request.method,
            request.url.path,
            response_time,
        )
    elif "thinking_mode" in request.url.path and response_time > 10:
        # LLM calls take 3-8s normally
        logger.warning(
            "Slow thinking mode: %s %s took %.3fs",
            request.method,
            request.url.path,
            response_time,
        )
    elif response_time > 5:
        # Other endpoints (static files, auth, etc.) should be fast
        logger.warning(
            "Slow request: %s %s took %.3fs",
            request.method,
            request.url.path,
            response_time,
        )

    return response


def _allowed_hosts() -> list[str]:
    """Host allowlist for ``TrustedHostMiddleware``.

    Reads ``ALLOWED_HOSTS`` (comma-separated). When unset, defaults to ``["*"]``
    (permissive) so existing dev/deployments are unaffected; set it in
    production to the public hostname(s) to mitigate Host-header injection and
    cache poisoning. ``localhost``/``127.0.0.1`` are always permitted for
    health checks and local probes.
    """
    raw = os.getenv("ALLOWED_HOSTS", "").strip()
    if not raw:
        return ["*"]
    hosts = [h.strip() for h in raw.split(",") if h.strip()]
    if not hosts:
        return ["*"]
    for local in ("localhost", "127.0.0.1"):
        if local not in hosts:
            hosts.append(local)
    return hosts


def setup_middleware(app: FastAPI):
    """
    Register all middleware with the FastAPI application.

    Order matters - middleware is executed in reverse order of registration.
    """
    # Host header validation (mitigates Host-header injection / cache poisoning).
    # Rejects requests whose Host is not in ALLOWED_HOSTS before they reach
    # route handlers. Permissive by default; enforced when ALLOWED_HOSTS is set.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts())

    # CORS Middleware
    # Extract server URL once to avoid linter warnings about constant access
    base_server_url = config.server_url
    if config.debug:
        # Development: Allow multiple origins
        allowed_origins = [
            base_server_url,
            "http://localhost:3000",
            "http://localhost:9527",
            "http://127.0.0.1:9527",
            "http://localhost:41732",
            "http://127.0.0.1:41732",
        ]
    else:
        # Production: Restrict to specific origins
        allowed_origins = [base_server_url]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=(
            r"^http://(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?$"
            if config.debug
            else None
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["ETag", "X-MG-Diagram-Id", "X-MG-Save-Error", "Content-Disposition"],
    )

    # GZip Compression with PDF exclusion
    # Use custom SelectiveGZipMiddleware that excludes PDF files to support range requests
    app.add_middleware(SelectiveGZipMiddleware, minimum_size=1000)

    # Custom middleware (registered as decorators, executed in order)
    # Note: Middleware executes in reverse order of registration
    # So log_requests runs first, then add_cache_control_headers, etc.
    app.middleware("http")(block_chat_static_uploads)
    app.middleware("http")(block_showcase_static_uploads)
    app.middleware("http")(enforce_streaming_body_limit)
    app.middleware("http")(limit_request_body_size)
    app.middleware("http")(abuseipdb_middleware)
    app.middleware("http")(csrf_protection)
    app.middleware("http")(add_security_headers)
    app.middleware("http")(add_cache_control_headers)
    app.middleware("http")(ensure_pdf_range_support)  # Safety net for PDF headers
    app.middleware("http")(log_requests)
    app.middleware("http")(feature_flag_gate)
    app.middleware("http")(auth_context_middleware)
    app.middleware("http")(vpn_cn_geo_middleware)
