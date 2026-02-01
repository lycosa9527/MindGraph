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
"""

import time
import json
import secrets
import logging
from urllib.parse import urlparse
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.middleware.gzip import GZipResponder
from config.settings import config
from services.auth.security_logger import security_log

logger = logging.getLogger(__name__)

# Maximum request body size (5MB) - prevents DoS attacks via large payloads
MAX_REQUEST_BODY_SIZE = 5 * 1024 * 1024  # 5MB


def is_https(request: Request) -> bool:
    """Check if request is over HTTPS."""
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
    if forwarded_proto == "https":
        return True
    if hasattr(request.url, 'scheme') and request.url.scheme == "https":
        return True
    return False


async def limit_request_body_size(request: Request, call_next):
    """
    Limit request body size to prevent DoS attacks.

    Rejects requests with Content-Length exceeding MAX_REQUEST_BODY_SIZE.
    This protects against attackers trying to exhaust server memory/disk
    by sending extremely large payloads (e.g., 100MB diagram specs).

    Note: This checks Content-Length header, which can be spoofed.
    For complete protection, also limit at reverse proxy level (Nginx).
    """
    content_length = request.headers.get('content-length')
    if content_length:
        try:
            size = int(content_length)
            if size > MAX_REQUEST_BODY_SIZE:
                client_ip = request.client.host if request.client else 'unknown'
                security_log.input_validation_failed(
                    field="request_body",
                    reason=(
                        f"size {size / 1024 / 1024:.1f}MB exceeds "
                        f"{MAX_REQUEST_BODY_SIZE / 1024 / 1024:.0f}MB limit"
                    ),
                    ip=client_ip,
                    value_size=size
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request body too large. Maximum size is {MAX_REQUEST_BODY_SIZE // 1024 // 1024}MB"
                    }
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
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        # Skip CSRF check for:
        # - Public endpoints (login, register, etc.)
        # - API endpoints that use API keys (different auth mechanism)
        # - Health checks
        skip_paths = [
            '/api/auth/login',
            '/api/auth/register',
            '/api/auth/demo/verify',
            '/api/frontend_log',
            '/api/frontend_log_batch',
            '/api/gewe/webhook',
            '/health',
            '/health/',
            '/docs',
            '/redoc',
            '/openapi.json'
        ]

        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)

        # Validate Origin header for cross-origin requests
        origin = request.headers.get('Origin')
        _referer = request.headers.get('Referer')  # Available for future use

        if origin:
            # Extract host from origin
            try:
                origin_host = urlparse(origin).netloc
                request_host = request.url.netloc

                # Allow same-origin requests
                if origin_host == request_host:
                    pass  # Same origin, allow
                else:
                    # Cross-origin: Check if origin is allowed
                    # In production, you might want to maintain a whitelist
                    # For now, we rely on SameSite cookies which provide good protection
                    logger.warning(
                        "Cross-origin request detected: Origin=%s, Host=%s",
                        origin_host, request_host
                    )
                    # Don't block - SameSite cookies will prevent CSRF
            except Exception as e:  # pylint: disable=broad-except
                logger.debug("Origin validation error (non-critical): %s", e)

        # Check for CSRF token in header (optional - for additional protection)
        csrf_token = request.headers.get('X-CSRF-Token')
        if csrf_token:
            # Validate CSRF token from cookie
            csrf_cookie = request.cookies.get('csrf_token')
            if csrf_cookie and csrf_token != csrf_cookie:
                logger.warning("CSRF token mismatch for %s", request.url.path)
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Invalid CSRF token"}
                )

    response = await call_next(request)

    # Set CSRF token cookie for authenticated users (if not already set)
    # This enables double-submit cookie pattern
    if request.cookies.get('access_token') and not request.cookies.get('csrf_token'):
        csrf_token = secrets.token_urlsafe(32)
        response.set_cookie(
            key='csrf_token',
            value=csrf_token,
            httponly=False,  # JavaScript needs to read it for X-CSRF-Token header
            secure=is_https(request) if hasattr(request, 'url') else False,
            samesite='strict',  # Strict SameSite for CSRF token
            max_age=7 * 24 * 60 * 60  # 7 days
        )

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
    - 'unsafe-inline' scripts: Required for config bootstrap and admin onclick handlers
    - 'unsafe-eval': Required for D3.js library (data transformations)
    - ws:/wss:: Required for VoiceAgent WebSocket connections
    - data: URIs: Required for canvas-to-image conversions
    - DEBUG mode: Allows Swagger UI CDN (cdn.jsdelivr.net) for /docs endpoint

    Reviewed: 2025-10-26 - All directives verified against actual codebase
    """
    response = await call_next(request)

    # Prevent clickjacking (stops site being embedded in iframes)
    response.headers["X-Frame-Options"] = "DENY"

    # Prevent MIME sniffing (stops browser from guessing content types)
    response.headers["X-Content-Type-Options"] = "nosniff"

    # XSS Protection (blocks reflected XSS attacks)
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Content Security Policy (controls what resources can load)
    # Tailored specifically for MindGraph's architecture
    # In DEBUG mode, allow Swagger UI CDN for /docs and /redoc endpoints
    if config.debug:
        # DEBUG mode: Allow Swagger UI resources from CDN (including source maps)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: http: https: blob: https://cdn.jsdelivr.net https://fastapi.tiangolo.com; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self' ws: wss: blob: https://cdn.jsdelivr.net; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
    else:
        # Production: Strict CSP without external CDN access
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: http: https: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss: blob:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

    # Referrer Policy (controls info sent in Referer header)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Permissions Policy (restrict access to browser features)
    # Only allow microphone (for VoiceAgent), disable everything else
    response.headers["Permissions-Policy"] = (
        "microphone=(self), "
        "camera=(), "
        "geolocation=(), "
        "payment=()"
    )

    return response


async def add_cache_control_headers(request: Request, call_next):
    """
    Add cache control headers for static files.

    Strategy:
    - Static files with version query string (?v=x.x.x): Cache for 1 year
    - Static files without version: Cache for 1 hour with revalidation
    - HTML pages: No cache (always fetch fresh)
    - API responses: No cache

    This ensures users always get the latest code when we update the VERSION file.
    """
    response = await call_next(request)

    path = request.url.path
    # Query string available via request.url.query if needed

    # Vue SPA assets (v5.0.0+) - served from /assets/
    if path.startswith('/assets/'):
        # Vue build assets are content-hashed, cache aggressively
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    # HTML pages: no cache
    elif path.endswith('.html') or path in ['/', '/editor', '/debug', '/auth', '/admin', '/demo']:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response


class SelectiveGZipMiddleware:
    """
    GZip middleware that excludes PDF files from compression.
    
    PDF files must not be compressed because:
    1. They are already compressed internally
    2. Compression breaks HTTP range requests needed for lazy loading
    3. Range requests require byte-level accuracy which is lost with compression
    """

    def __init__(self, app: ASGIApp, minimum_size: int = 1000, compresslevel: int = 9):
        self.app = app
        self.minimum_size = minimum_size
        self.compresslevel = compresslevel

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            # Check if this is a PDF file endpoint BEFORE processing
            is_pdf_endpoint = (
                path.startswith("/api/library/documents/") and "/file" in path
            )

            if is_pdf_endpoint:
                # Skip compression for PDF files - pass through directly
                # This preserves range request support
                await self.app(scope, receive, send)
            else:
                # Use GZipResponder for other responses (standard compression)
                responder = GZipResponder(
                    self.app,
                    minimum_size=self.minimum_size,
                    compresslevel=self.compresslevel
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
    content_type = response.headers.get('Content-Type', '')
    path = request.url.path

    if content_type == 'application/pdf' or (
        path.startswith('/api/library/documents/') and '/file' in path
    ):
        # Ensure Accept-Ranges is set for range request support
        if 'Accept-Ranges' not in response.headers:
            response.headers['Accept-Ranges'] = 'bytes'
        # Ensure Content-Encoding is not set (shouldn't be, but double-check)
        if 'Content-Encoding' in response.headers:
            encoding = response.headers['Content-Encoding']
            if encoding in ('gzip', 'deflate', 'br'):
                logger.warning(
                    "[Middleware] PDF file was compressed (%s), removing compression header. "
                    "This breaks range requests! Path: %s",
                    encoding, path
                )
                del response.headers['Content-Encoding']

    return response


async def log_requests(request: Request, call_next):
    """
    Log all HTTP requests and responses with timing information.
    Handles request/response lifecycle events.
    """
    start_time = time.time()

    # For Vue assets, include version info in log for debugging
    log_path = request.url.path
    if request.url.path.startswith('/assets/') and request.url.query:
        log_path = f"{request.url.path}?{request.url.query}"

    # For POST requests to generate_graph, check if it's autocomplete before processing
    # This allows us to set appropriate slow warning thresholds
    is_autocomplete_request = False
    if request.method == 'POST' and 'generate_graph' in request.url.path:
        try:
            body = await request.body()
            if body:
                body_data = json.loads(body)
                is_autocomplete_request = body_data.get('request_type') == 'autocomplete'
                # Recreate request body stream for downstream consumption
                async def _receive_body():
                    return {'type': 'http.request', 'body': body}
                request._receive = _receive_body  # pylint: disable=protected-access
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass

    # Process request
    response = await call_next(request)

    # Log combined request/response to save space
    response_time = time.time() - start_time
    logger.debug(
        "Request: %s %s from %s Response: %s in %.3fs",
        request.method, log_path, request.client.host, response.status_code, response_time
    )

    # Monitor slow requests (thresholds based on endpoint type)
    if 'generate_png' in request.url.path and response_time > 20:
        logger.warning(
            "Slow PNG generation: %s %s took %.3fs",
            request.method, request.url.path, response_time
        )
    elif 'generate_graph' in request.url.path:
        if is_autocomplete_request:
            # Auto-complete: Each LLM call takes 3-5s, total ~10-12s for 3-4 models
            # Based on actual performance data from CHANGELOG: first result ~3s, total ~10-12s
            # Warn if individual LLM call exceeds 8s (should be 3-5s normally)
            if response_time > 8:
                logger.warning(
                    "Slow auto-complete generation: %s %s took %.3fs "
                    "(expected 3-5s per LLM, total ~10-12s for all models)",
                    request.method, request.url.path, response_time
                )
        else:
            # Initial generation: Should be fast, 2-8s typical
            # Based on actual performance: Qwen typically 2-5s, other models 3-8s
            if response_time > 5:
                logger.warning(
                    "Slow graph generation: %s %s took %.3fs (expected 2-8s)",
                    request.method, request.url.path, response_time
                )
    elif 'node_palette' in request.url.path and response_time > 10:
        # Node Palette streams from 4 LLMs, 5-8s is normal
        logger.warning(
            "Slow node palette: %s %s took %.3fs",
            request.method, request.url.path, response_time
        )
    elif 'thinking_mode' in request.url.path and response_time > 10:
        # LLM calls take 3-8s normally
        logger.warning(
            "Slow thinking mode: %s %s took %.3fs",
            request.method, request.url.path, response_time
        )
    elif response_time > 5:
        # Other endpoints (static files, auth, etc.) should be fast
        logger.warning(
            "Slow request: %s %s took %.3fs",
            request.method, request.url.path, response_time
        )

    return response


def setup_middleware(app: FastAPI):
    """
    Register all middleware with the FastAPI application.
    
    Order matters - middleware is executed in reverse order of registration.
    """
    # CORS Middleware
    # Extract server URL once to avoid linter warnings about constant access
    base_server_url = config.server_url
    if config.debug:
        # Development: Allow multiple origins
        allowed_origins = [
            base_server_url,
            'http://localhost:3000',
            'http://127.0.0.1:9527'
        ]
    else:
        # Production: Restrict to specific origins
        allowed_origins = [base_server_url]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip Compression with PDF exclusion
    # Use custom SelectiveGZipMiddleware that excludes PDF files to support range requests
    app.add_middleware(SelectiveGZipMiddleware, minimum_size=1000)

    # Custom middleware (registered as decorators, executed in order)
    # Note: Middleware executes in reverse order of registration
    # So log_requests runs first, then add_cache_control_headers, etc.
    app.middleware("http")(limit_request_body_size)
    app.middleware("http")(csrf_protection)
    app.middleware("http")(add_security_headers)
    app.middleware("http")(add_cache_control_headers)
    app.middleware("http")(ensure_pdf_range_support)  # Safety net for PDF headers
    app.middleware("http")(log_requests)
