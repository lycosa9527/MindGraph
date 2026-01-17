"""
Exception handlers for MindGraph application.

Handles:
- Request validation errors (422)
- HTTP exceptions
- General unhandled exceptions
"""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from config.settings import config

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors (422 Unprocessable Entity).

    These occur when request body/parameters don't match the expected schema.
    Common causes: missing required fields, wrong data types, invalid formats.
    """
    path = getattr(request.url, 'path', '') if request and request.url else ''

    # Extract validation errors
    errors = exc.errors() if hasattr(exc, 'errors') else []
    error_details = []
    for error in errors:
        loc = error.get('loc', [])
        msg = error.get('msg', '')
        error_details.append(f"{'.'.join(str(x) for x in loc)}: {msg}")

    # Log at DEBUG level for common validation issues (expected client errors)
    # Log at WARNING level for unusual validation errors
    error_summary = '; '.join(error_details[:3])  # Show first 3 errors
    if len(error_details) > 3:
        error_summary += f" ... and {len(error_details) - 3} more"

    logger.debug("Request validation error on %s: %s", path, error_summary)

    return JSONResponse(
        status_code=422,
        content={
            "detail": error_details,
            "message": "Request validation failed. Please check your request parameters."
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle HTTP exceptions.

    Returns FastAPI-standard format: {"detail": "error message"}
    This matches FastAPI's default HTTPException response format.
    """
    path = getattr(request.url, 'path', '') if request and request.url else ''
    detail = exc.detail or ""

    # Suppress warnings for expected security checks:
    # 1. Admin access checks (403 on /api/auth/admin/* endpoints)
    #    The admin button ("后台") calls /api/auth/admin/stats to check admin status
    # 2. Token expiration checks (401 with "Invalid or expired token")
    #    Frontend periodically checks authentication status via /api/auth/me
    # 3. Request validation errors (400) - these are client errors, log at DEBUG
    if exc.status_code == 403 and path.startswith("/api/auth/admin/"):
        logger.debug("HTTP %s: %s (expected admin check)", exc.status_code, exc.detail)
    elif exc.status_code == 401 and "Invalid or expired token" in detail:
        logger.debug("HTTP %s: %s (expected token expiration check)", exc.status_code, exc.detail)
    elif exc.status_code == 400:
        # 400 Bad Request - usually client errors (invalid parameters, malformed requests)
        # Log at DEBUG level to reduce noise (these are expected client errors)
        logger.debug("HTTP %s on %s: %s", exc.status_code, path, exc.detail)
    else:
        logger.warning("HTTP %s: %s", exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}  # Use "detail" to match FastAPI standard
    )


async def general_exception_handler(_request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    logger.error("Unhandled exception: %s: %s", type(exc).__name__, exc, exc_info=True)

    error_response = {"error": "An unexpected error occurred. Please try again later."}

    # Add debug info in development mode
    if config.debug:
        error_response["debug"] = str(exc)

    return JSONResponse(
        status_code=500,
        content=error_response
    )


def setup_exception_handlers(app: FastAPI):
    """
    Register all exception handlers with the FastAPI application.
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
