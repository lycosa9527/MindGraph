"""
Environment flags and object-key helpers for COS mirror sync.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
from typing import Literal

from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    cos_object_key,
    normalized_cos_prefix,
)

CosSyncRole = Literal["off", "publisher", "consumer"]

_CROWDSEC_REL = "sync/crowdsec"
_QDRANT_REL = "sync/qdrant"
_CELERY_REL = "sync/celery"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default).lower()).strip().lower()
    return raw in ("1", "true", "yes", "on")


def cos_sync_enabled() -> bool:
    """True when COS mirror sync is enabled and bucket credentials exist."""
    if not _env_bool("COS_SYNC_ENABLED", False):
        return False
    return cos_credentials_configured()


def cos_sync_role() -> CosSyncRole:
    """Return publisher, consumer, or off."""
    if not cos_sync_enabled():
        return "off"
    raw = os.getenv("COS_SYNC_ROLE", "off").strip().lower()
    if raw in ("publisher", "source"):
        return "publisher"
    if raw in ("consumer", "replica"):
        return "consumer"
    return "off"


def is_cos_publisher() -> bool:
    """True when this host publishes artifacts to COS."""
    return cos_sync_role() == "publisher"


def is_cos_consumer() -> bool:
    """True when this host consumes artifacts from COS."""
    return cos_sync_role() == "consumer"


def crowdsec_blocklist_cos_key() -> str:
    """COS key for CrowdSec blocklist plaintext."""
    return cos_object_key(f"{_CROWDSEC_REL}/blocklist.txt")


def crowdsec_meta_cos_key() -> str:
    """COS key for CrowdSec blocklist meta JSON."""
    return cos_object_key(f"{_CROWDSEC_REL}/meta.json")


def qdrant_meta_cos_key() -> str:
    """COS key for Qdrant release meta JSON."""
    return cos_object_key(f"{_QDRANT_REL}/meta.json")


def qdrant_tarball_cos_key(version: str, arch: str) -> str:
    """COS key for Qdrant release tarball."""
    safe_version = version.lstrip("v")
    return cos_object_key(f"{_QDRANT_REL}/v{safe_version}/qdrant-{arch}.tar.gz")


def qdrant_download_source() -> str:
    """auto | cos | github for setup.py download preference."""
    raw = os.getenv("QDRANT_DOWNLOAD_SOURCE", "auto").strip().lower()
    if raw in ("cos", "github"):
        return raw
    return "auto"


def qdrant_cos_auto_install() -> bool:
    """Consumer auto-install when running as root."""
    return _env_bool("QDRANT_COS_AUTO_INSTALL", False)


def celery_meta_cos_key() -> str:
    """COS key for Celery release meta JSON."""
    return cos_object_key(f"{_CELERY_REL}/meta.json")


def celery_wheel_cos_key(version: str, wheel_filename: str) -> str:
    """COS key for Celery PyPI wheel."""
    safe_version = version.lstrip("v")
    return cos_object_key(f"{_CELERY_REL}/v{safe_version}/{wheel_filename}")


def cos_config_snapshot() -> dict:
    """Read-only config for admin API (no secrets)."""
    return {
        "sync_enabled": cos_sync_enabled(),
        "sync_role": cos_sync_role(),
        "backup_enabled": _env_bool("COS_BACKUP_ENABLED", False),
        "bucket": os.getenv("COS_BUCKET", "").strip() or None,
        "region": os.getenv("COS_REGION", "ap-beijing").strip(),
        "key_prefix": normalized_cos_prefix(),
        "credentials_configured": cos_credentials_configured(),
    }
