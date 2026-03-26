"""
Runtime feature-flag gate for HTTP requests.

After reloading .env into the process, ``config.FEATURE_*`` may change while
routers registered at startup remain mounted. This middleware blocks requests
to feature-specific URL prefixes when the corresponding flag is false.
"""

from fastapi import Request
from starlette.responses import JSONResponse

from config.settings import config

# Longest prefix first (most specific match).
_PATH_FLAG_ATTRS: tuple[tuple[str, str], ...] = (
    ("/api/auth/admin/teacher-usage", "FEATURE_TEACHER_USAGE"),
    ("/api/knowledge-space", "FEATURE_KNOWLEDGE_SPACE"),
    ("/api/school-zone", "FEATURE_SCHOOL_ZONE"),
    ("/api/debateverse", "FEATURE_DEBATEVERSE"),
    ("/api/community", "FEATURE_COMMUNITY"),
    ("/api/library", "FEATURE_LIBRARY"),
    ("/api/askonce", "FEATURE_ASKONCE"),
    ("/api/devices", "FEATURE_SMART_RESPONSE"),
    ("/api/gewe", "FEATURE_GEWE"),
    ("/api/chat", "FEATURE_WORKSHOP_CHAT"),
)


def _feature_enabled(attr_name: str) -> bool:
    return bool(getattr(config, attr_name, False))


async def feature_flag_gate(request: Request, call_next):
    """Return 404 JSON when a gated path is used but its feature is off."""
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    for prefix, attr in _PATH_FLAG_ATTRS:
        if path.startswith(prefix) and not _feature_enabled(attr):
            return JSONResponse(
                status_code=404,
                content={"detail": "Feature is disabled"},
            )
    return await call_next(request)
