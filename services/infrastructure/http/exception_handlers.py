"""
Exception handlers for MindGraph application.

Handles:
- Request validation errors (422)
- HTTP exceptions
- General unhandled exceptions
"""

import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from config.settings import config
from services.infrastructure.monitoring.critical_alert import CriticalAlertService

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
    # 4. Missing library pages/bookmarks (404) - expected when pages don't exist or bookmarks aren't created
    #    Frontend checks for bookmarks and may request pages that don't exist if total_pages is incorrect
    if exc.status_code == 403 and path.startswith("/api/auth/admin/"):
        logger.debug("HTTP %s: %s (expected admin check)", exc.status_code, exc.detail)
    elif exc.status_code == 401 and "Invalid or expired token" in detail:
        logger.debug("HTTP %s: %s (expected token expiration check)", exc.status_code, exc.detail)
    elif exc.status_code == 400:
        # 400 Bad Request - usually client errors (invalid parameters, malformed requests)
        # Log at DEBUG level to reduce noise (these are expected client errors)
        logger.debug("HTTP %s on %s: %s", exc.status_code, path, exc.detail)
    elif exc.status_code == 404:
        # 404 Not Found - check if it's an expected case
        if path.startswith("/api/library/documents/") and "/pages/" in path:
            # Missing page image - may happen if total_pages is incorrect or file is missing
            logger.debug("HTTP %s: %s (page may not exist)", exc.status_code, exc.detail)
        elif path.startswith("/api/library/documents/") and "/bookmarks/" in path:
            # Missing bookmark - expected when checking if bookmark exists
            logger.debug("HTTP %s: %s (bookmark check)", exc.status_code, exc.detail)
        else:
            # Other 404s - log at warning level
            logger.warning("HTTP %s: %s", exc.status_code, exc.detail)
    else:
        logger.warning("HTTP %s: %s", exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}  # Use "detail" to match FastAPI standard
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    exception_type = type(exc).__name__
    exception_message = str(exc)
    request_path = getattr(request.url, 'path', '') if request and request.url else ''

    stack_trace = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    logger.error("Unhandled exception: %s: %s", exception_type, exception_message, exc_info=True)

    error_response = {"error": "An unexpected error occurred. Please try again later."}

    # Add debug info in development mode
    if config.debug:
        error_response["debug"] = str(exc)

    # Check if this is a critical exception that warrants SMS alert
    is_critical = _is_critical_exception(exception_type, exception_message)

    if is_critical:
        try:
            await CriticalAlertService.send_unhandled_exception_alert(
                component="Application",
                exception_type=exception_type,
                error_message=exception_message,
                stack_trace=stack_trace,
                request_path=request_path
            )
        except Exception as alert_error:  # pylint: disable=broad-except
            logger.error("Failed to send unhandled exception alert: %s", alert_error, exc_info=True)

    return JSONResponse(
        status_code=500,
        content=error_response
    )


def _is_critical_exception(exception_type: str, exception_message: str) -> bool:
    """
    Determine if an exception is critical and warrants SMS alert.

    Args:
        exception_type: Exception class name
        exception_message: Exception message

    Returns:
        True if critical, False otherwise
    """
    critical_exception_types = (
        "DatabaseError",
        "OperationalError",
        "IntegrityError",
        "ConnectionError",
        "TimeoutError",
        "MemoryError",
        "OSError",
        "SystemError",
        "RuntimeError"
    )

    critical_keywords = (
        "database",
        "corruption",
        "connection",
        "memory",
        "disk",
        "file system",
        "critical",
        "fatal"
    )

    if exception_type in critical_exception_types:
        return True

    message_lower = exception_message.lower()
    if any(keyword in message_lower for keyword in critical_keywords):
        return True

    return False


def setup_exception_handlers(app: FastAPI):
    """
    Register all exception handlers with the FastAPI application.
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
