"""Showcase server-side cover feature flag."""

from __future__ import annotations

import os

from config.settings import config


def showcase_server_covers_enabled() -> bool:
    """True when teaching-design covers should be generated on the server.

    Default: on when ``COS_SHOWCASE_ENABLED`` (works with COS or local fallback).
    Set ``SHOWCASE_SERVER_COVERS=false`` to disable; ``true`` forces on.
    """
    raw = (os.environ.get("SHOWCASE_SERVER_COVERS") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return bool(config.COS_SHOWCASE_ENABLED)


def celery_worker_needed_for_app() -> bool:
    """True when the app should start/monitor a Celery worker."""
    return bool(config.FEATURE_KNOWLEDGE_SPACE) or showcase_server_covers_enabled()
