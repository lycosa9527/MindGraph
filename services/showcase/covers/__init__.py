"""Server-side Showcase teaching-design cover generation.

Keep this package init light: importing ``host_deps`` / ``config`` from
infrastructure launch paths must not pull Redis/DB via ``generate``.
"""

from services.showcase.covers.config import (
    celery_worker_needed_for_app,
    showcase_server_covers_enabled,
)

__all__ = [
    "celery_worker_needed_for_app",
    "showcase_server_covers_enabled",
]
