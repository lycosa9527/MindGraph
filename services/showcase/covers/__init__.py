"""Server-side Showcase teaching-design cover generation."""

from services.showcase.covers.config import (
    celery_worker_needed_for_app,
    showcase_server_covers_enabled,
)
from services.showcase.covers.generate import (
    attachment_key_in_post_scope,
    generate_showcase_cover,
)

__all__ = [
    "attachment_key_in_post_scope",
    "celery_worker_needed_for_app",
    "generate_showcase_cover",
    "showcase_server_covers_enabled",
]
