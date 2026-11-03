"""Store personal-knowledge markdown where VibeFlow already watches.

The pipeline watches ``vibeflow/source/``. The server name is the next folder,
so local objects are ``vibeflow/source/dev_roy/{user}/{package}/{document}/``.
The table-of-contents manifest lives under ``{owner}/knowledge/toc/`` so it is not embedded.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List
from urllib.parse import quote

from services.knowledge.personal_knowledge_log import log_personal_knowledge
from services.knowledge.vibeflow_cut import VibeflowPiece
from services.utils.aliyun_oss_client import (
    delete_object,
    get_oss_bucket,
    list_prefix,
    oss_credentials_configured,
)

logger = logging.getLogger(__name__)

try:
    from oss2.exceptions import OssError as _OssError
except ImportError:
    _OssError = None

VIBE_SOURCE_ROOT = "vibeflow/source"
TOC_ROOT = "knowledge/toc"


def vibe_owner_prefix() -> str:
    """First segment of ``OSS_KEY_PREFIX`` (``dev_roy`` when the backup prefix is ``dev_roy/backups``)."""
    prefix = os.getenv("OSS_KEY_PREFIX", "").strip().strip("/")
    head = prefix.split("/", 1)[0] if prefix else ""
    return head or "local"


def document_prefix(user_id: int, package_id: int, document_id: int) -> str:
    """Object prefix for one personal-knowledge document, inside the watched pipeline root."""
    return f"{VIBE_SOURCE_ROOT}/{vibe_owner_prefix()}/{user_id}/{package_id}/{document_id}"


def legacy_document_prefix(user_id: int, package_id: int, document_id: int) -> str:
    """Earlier prefix that sat outside the pipeline watch root."""
    return f"{vibe_owner_prefix()}/{VIBE_SOURCE_ROOT}/{user_id}/{package_id}/{document_id}"


def toc_object_key(user_id: int, package_id: int, document_id: int) -> str:
    """Manifest key outside the VibeFlow prefix."""
    return f"{vibe_owner_prefix()}/{TOC_ROOT}/{user_id}/{package_id}/{document_id}.json"


def package_toc_prefix(user_id: int, package_id: int) -> str:
    """Manifest prefix for every document in one folder."""
    return f"{vibe_owner_prefix()}/{TOC_ROOT}/{user_id}/{package_id}"


def _tag_header(tags: Dict[str, str]) -> str:
    return "&".join(f"{quote(key, safe='')}={quote(value, safe='')}" for key, value in tags.items())


def _oss_errors() -> tuple:
    errors: List[type] = [OSError, TimeoutError, RuntimeError, ValueError]
    if _OssError is not None:
        errors.insert(0, _OssError)
    return tuple(errors)


def _put_bytes(key: str, payload: bytes, content_type: str, tags: Dict[str, str] | None = None) -> bool:
    bucket = get_oss_bucket()
    if bucket is None:
        return False
    headers = {"Content-Type": content_type}
    if tags:
        headers["x-oss-tagging"] = _tag_header(tags)
    try:
        bucket.put_object(key, payload, headers=headers)
    except _oss_errors() as exc:
        logger.error("[VibeFlow] put failed key=%s: %s", key, exc)
        return False
    return True


def upload_pieces(
    user_id: int,
    package_id: int,
    document_id: int,
    pieces: List[VibeflowPiece],
) -> bool:
    """Write markdown objects and the manifest. False when any write fails."""
    if not oss_credentials_configured():
        log_personal_knowledge(
            "oss_refused",
            reason="oss_not_configured",
            user=user_id,
            package=package_id,
            document=document_id,
        )
        return False
    if not pieces:
        log_personal_knowledge(
            "oss_refused",
            reason="no_pieces",
            user=user_id,
            package=package_id,
            document=document_id,
        )
        return False
    prefix = document_prefix(user_id, package_id, document_id)
    server = vibe_owner_prefix()
    log_personal_knowledge(
        "sending_oss",
        user=user_id,
        package=package_id,
        document=document_id,
        pieces=len(pieces),
        server=server,
        prefix=prefix,
    )
    manifest: List[Dict[str, Any]] = []
    for piece in pieces:
        name = f"{piece.index:04d}.md"
        key = f"{prefix}/{piece.section_number}/{name}"
        body = piece.text
        if piece.title:
            body = f"# {piece.title}\n\n{piece.text}"
        tags = {
            "user_id": str(user_id),
            "package_id": str(package_id),
            "document_id": str(document_id),
            "server": server,
            "section_number": piece.section_number,
        }
        if not _put_bytes(key, body.encode("utf-8"), "text/markdown; charset=utf-8", tags):
            log_personal_knowledge(
                "oss_failed",
                user=user_id,
                package=package_id,
                document=document_id,
                section=piece.section_number,
                index=piece.index,
                written=len(manifest),
            )
            return False
        manifest.append(
            {
                "section_number": piece.section_number,
                "title": piece.title,
                "index": piece.index,
                "key": key,
            }
        )
    manifest_key = toc_object_key(user_id, package_id, document_id)
    payload = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    if not _put_bytes(manifest_key, payload, "application/json"):
        log_personal_knowledge(
            "oss_failed",
            reason="manifest",
            user=user_id,
            package=package_id,
            document=document_id,
            objects=len(manifest),
        )
        return False
    log_personal_knowledge(
        "oss_stored",
        user=user_id,
        package=package_id,
        document=document_id,
        objects=len(manifest),
        server=server,
    )
    return True


def delete_document_objects(user_id: int, package_id: int, document_id: int) -> None:
    """Remove a document's markdown and its manifest."""
    log_personal_knowledge(
        "clearing_oss",
        user=user_id,
        package=package_id,
        document=document_id,
    )
    prefixes = (
        document_prefix(user_id, package_id, document_id),
        legacy_document_prefix(user_id, package_id, document_id),
    )
    for prefix in prefixes:
        for item in list_prefix(prefix):
            delete_object(str(item["key"]))
    delete_object(toc_object_key(user_id, package_id, document_id))


def read_object_text(key: str) -> str:
    """Read one object as UTF-8 text."""
    bucket = get_oss_bucket()
    if bucket is None:
        return ""
    try:
        result = bucket.get_object(key)
        return result.read().decode("utf-8")
    except _oss_errors() as exc:
        logger.warning("[VibeFlow] read failed key=%s: %s", key, exc)
        return ""


def load_package_manifest(user_id: int, package_id: int) -> List[Dict[str, Any]]:
    """Return every manifest entry for a personal-knowledge folder."""
    entries: List[Dict[str, Any]] = []
    for item in list_prefix(package_toc_prefix(user_id, package_id), suffix_filter=".json"):
        raw = read_object_text(str(item["key"]))
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            entries.extend(entry for entry in parsed if isinstance(entry, dict))
    return entries
