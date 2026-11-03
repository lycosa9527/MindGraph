"""Query the VibeFlow vector index.

The index ``mindgraph`` in vector bucket ``mindchunk`` is 2560-dimensional
Euclidean. VibeFlow embeds each watched object with ``qwen3-vl-embedding``.
The query vector uses that same model and is not L2-normalized here, so it
stays on the scale the pipeline wrote. Rank fusion lives in
``vibeflow_rrf``; this module does not call a DashScope rerank model.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import logging
import os
from email.utils import format_datetime
from typing import Any, Dict, List
from urllib.parse import quote

import httpx

from config.dashscope_urls import build_dashscope_headers
from config.settings import config
from services.utils.aliyun_oss_client import (
    get_oss_bucket,
    oss_access_key_id,
    oss_access_key_secret,
    oss_region,
)

logger = logging.getLogger(__name__)

try:
    from oss2.exceptions import OssError as _OssError
except ImportError:
    _OssError = None

VECTOR_BUCKET = "mindchunk"
VECTOR_INDEX = "mindgraph"
VECTOR_DIMENSION = 2560
EMBED_MODEL = "qwen3-vl-embedding"
QUERY_TOP_K = 30


def _vector_errors() -> tuple:
    errors: List[type] = [httpx.HTTPError, json.JSONDecodeError, OSError, RuntimeError, ValueError, TypeError]
    if _OssError is not None:
        errors.append(_OssError)
    return tuple(errors)


class _AccountHolder:
    """Cached OSS account id from the object-bucket owner."""

    account_id: str = ""


def _vector_bucket() -> str:
    return os.getenv("OSS_VECTOR_BUCKET", VECTOR_BUCKET).strip() or VECTOR_BUCKET


def _vector_index() -> str:
    return os.getenv("OSS_VECTOR_INDEX", VECTOR_INDEX).strip() or VECTOR_INDEX


def _account_id() -> str:
    if _AccountHolder.account_id:
        return _AccountHolder.account_id
    bucket = get_oss_bucket()
    if bucket is None:
        return ""
    try:
        info = bucket.get_bucket_info()
        owner = getattr(info, "owner", None)
        account = str(getattr(owner, "id", "") or "").strip()
    except _vector_errors() as exc:
        logger.warning("[VibeFlow] account id lookup failed: %s", exc)
        return ""
    _AccountHolder.account_id = account
    return account


def _sign_headers(operation: str, iso: str, region: str, account: str, vector_bucket: str) -> Dict[str, str]:
    date = iso[:8]
    signed = {
        "content-type": "application/json",
        "x-oss-content-sha256": "UNSIGNED-PAYLOAD",
        "x-oss-date": iso,
    }
    canonical_headers = "".join(f"{key}:{signed[key]}\n" for key in sorted(signed))
    canonical_uri = quote(f"/acs:ossvector:{region}:{account}:{vector_bucket}/", safe="/")
    canonical = f"POST\n{canonical_uri}\n{operation}\n{canonical_headers}\n\nUNSIGNED-PAYLOAD"
    scope = f"{date}/{region}/oss/aliyun_v4_request"
    string_to_sign = "\n".join(
        (
            "OSS4-HMAC-SHA256",
            iso,
            scope,
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )
    )
    key = ("aliyun_v4" + oss_access_key_secret()).encode("utf-8")
    for part in (date, region, "oss", "aliyun_v4_request"):
        key = hmac.new(key, part.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    credential = f"{oss_access_key_id()}/{scope}"
    return {
        "Content-Type": "application/json",
        "x-oss-content-sha256": "UNSIGNED-PAYLOAD",
        "x-oss-date": iso,
        "Authorization": f"OSS4-HMAC-SHA256 Credential={credential},Signature={signature}",
    }


def _post_vector(operation: str, body: Dict[str, Any]) -> Dict[str, Any]:
    account = _account_id()
    region = oss_region()
    vector_bucket = _vector_bucket()
    if not account or not region or not oss_access_key_id() or not oss_access_key_secret():
        return {}
    now = datetime.datetime.now(datetime.timezone.utc)
    iso = now.strftime("%Y%m%dT%H%M%SZ")
    headers = _sign_headers(operation, iso, region, account, vector_bucket)
    headers["Date"] = format_datetime(now, usegmt=True)
    host = f"{vector_bucket}-{account}.{region}.oss-vectors.aliyuncs.com"
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    try:
        response = httpx.post(f"https://{host}/?{operation}", content=payload, headers=headers, timeout=60.0)
        response.raise_for_status()
        parsed = response.json()
    except _vector_errors() as exc:
        logger.warning("[VibeFlow] %s failed: %s", operation, exc)
        return {}
    return parsed if isinstance(parsed, dict) else {}


def embed_branch_query(text: str) -> List[float]:
    """Embed one branch label with the same model VibeFlow uses."""
    query = (text or "").strip()
    api_key = (config.QWEN_API_KEY or "").strip()
    if not query or not api_key:
        return []
    url = f"{config.DASHSCOPE_API_URL.rstrip('/')}/services/embeddings/multimodal-embedding/multimodal-embedding"
    payload = {
        "model": os.getenv("VIBE_EMBEDDING_MODEL", EMBED_MODEL).strip() or EMBED_MODEL,
        "input": {"contents": [{"text": query}]},
        "parameters": {"dimension": VECTOR_DIMENSION, "output_type": "dense"},
    }
    try:
        response = httpx.post(
            url,
            headers=build_dashscope_headers(api_key, workspace_id=config.DASHSCOPE_WORKSPACE_ID),
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        parsed = response.json()
        embeddings = parsed["output"]["embeddings"]
        vector = embeddings[0]["embedding"]
    except (KeyError, IndexError, *_vector_errors()) as exc:
        logger.warning("[VibeFlow] query embedding failed: %s", exc)
        return []
    if not isinstance(vector, list) or len(vector) != VECTOR_DIMENSION:
        logger.warning("[VibeFlow] query embedding dimension %s", len(vector) if isinstance(vector, list) else 0)
        return []
    return [float(item) for item in vector]


def query_similar_keys(user_id: int, package_id: int, vector: List[float], top_k: int = QUERY_TOP_K) -> List[str]:
    """Return object keys nearest to ``vector`` inside this user and folder."""
    if len(vector) != VECTOR_DIMENSION:
        return []
    body = {
        "indexName": _vector_index(),
        "queryVector": {"float32": vector},
        "topK": max(1, min(int(top_k), 100)),
        "returnDistance": False,
        "returnMetadata": True,
        "filter": {
            "$and": [
                {"user_id": {"$eq": str(user_id)}},
                {"package_id": {"$eq": str(package_id)}},
            ]
        },
    }
    parsed = _post_vector("queryVectors", body)
    keys: List[str] = []
    marker = f"/{user_id}/{package_id}/"
    for item in parsed.get("vectors") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        if marker not in key:
            continue
        keys.append(key)
    return keys
