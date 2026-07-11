"""DashScope HTTP endpoint builders (legacy + workspace MaaS domains).

When ``DASHSCOPE_WORKSPACE_ID`` is set, chat / compatible-mode / api/v1 URLs
are built from the workspace subdomain per Aliyun docs. Explicit ``QWEN_API_URL``
or ``DASHSCOPE_API_URL`` env vars always win.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Literal, Optional, TypedDict

DashScopeRegion = Literal[
    "cn-beijing",
    "ap-southeast-1",
    "us",
    "eu-central-1",
    "ap-northeast-1",
]

LEGACY_CHAT_COMPLETIONS_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
LEGACY_COMPATIBLE_MODE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LEGACY_API_V1_BASE = "https://dashscope.aliyuncs.com/api/v1/"
LEGACY_COMPATIBLE_API_BASE = "https://dashscope.aliyuncs.com/compatible-api/v1"
LEGACY_REALTIME_WS_BASE_CN = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
LEGACY_REALTIME_WS_BASE_INTL = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"

_REGION_ALIASES: dict[str, DashScopeRegion] = {
    "cn": "cn-beijing",
    "cn-beijing": "cn-beijing",
    "beijing": "cn-beijing",
    "china": "cn-beijing",
    "sg": "ap-southeast-1",
    "ap-southeast-1": "ap-southeast-1",
    "singapore": "ap-southeast-1",
    "intl": "ap-southeast-1",
    "international": "ap-southeast-1",
    "us": "us",
    "us-east": "us",
    "virginia": "us",
    "dashscope-us": "us",
    "eu-central-1": "eu-central-1",
    "frankfurt": "eu-central-1",
    "eu": "eu-central-1",
    "ap-northeast-1": "ap-northeast-1",
    "tokyo": "ap-northeast-1",
    "jp": "ap-northeast-1",
    "japan": "ap-northeast-1",
}

_LEGACY_HOST_BY_REGION: dict[DashScopeRegion, str] = {
    "cn-beijing": "dashscope.aliyuncs.com",
    "ap-southeast-1": "dashscope-intl.aliyuncs.com",
    "us": "dashscope-us.aliyuncs.com",
    "eu-central-1": "dashscope.aliyuncs.com",
    "ap-northeast-1": "dashscope.aliyuncs.com",
}


class DashScopeEndpointSummary(TypedDict):
    """Resolved endpoint mode for startup / debug logs."""

    mode: str
    region: str
    workspace_id: Optional[str]
    chat_completions_url: str
    api_v1_base: str
    compatible_mode_base: str
    realtime_ws_base: str


def normalize_dashscope_region(raw: Optional[str]) -> DashScopeRegion:
    """Map env aliases to a canonical DashScope region key."""
    key = str(raw or "cn-beijing").strip().lower()
    return _REGION_ALIASES.get(key, "cn-beijing")


def _clean_workspace_id(workspace_id: Optional[str]) -> Optional[str]:
    if not isinstance(workspace_id, str):
        return None
    cleaned = workspace_id.strip()
    return cleaned or None


def resolve_dashscope_host(
    *,
    workspace_id: Optional[str],
    region: DashScopeRegion,
) -> str:
    """
    Return HTTPS host for DashScope HTTP APIs.

    US (弗吉尼亚) uses a fixed host without workspace subdomain. Other regions
    use ``{workspaceId}.{region}.maas.aliyuncs.com`` when workspace id is set.
    """
    ws = _clean_workspace_id(workspace_id)
    if region == "us":
        return _LEGACY_HOST_BY_REGION["us"]
    if ws:
        return f"{ws}.{region}.maas.aliyuncs.com"
    return _LEGACY_HOST_BY_REGION[region]


def build_compatible_mode_base(
    *,
    workspace_id: Optional[str] = None,
    region: DashScopeRegion = "cn-beijing",
) -> str:
    """``https://…/compatible-mode/v1`` (OpenAI-compatible REST base)."""
    host = resolve_dashscope_host(workspace_id=workspace_id, region=region)
    return f"https://{host}/compatible-mode/v1"


def build_compatible_api_base(
    *,
    workspace_id: Optional[str] = None,
    region: DashScopeRegion = "cn-beijing",
) -> str:
    """``https://…/compatible-api/v1`` (rerank and related APIs)."""
    host = resolve_dashscope_host(workspace_id=workspace_id, region=region)
    return f"https://{host}/compatible-api/v1"


def build_api_v1_base(
    *,
    workspace_id: Optional[str] = None,
    region: DashScopeRegion = "cn-beijing",
) -> str:
    """``https://…/api/v1/`` (native DashScope REST base)."""
    host = resolve_dashscope_host(workspace_id=workspace_id, region=region)
    return f"https://{host}/api/v1/"


def build_chat_completions_url(
    *,
    workspace_id: Optional[str] = None,
    region: DashScopeRegion = "cn-beijing",
) -> str:
    """Full OpenAI-compatible chat completions URL."""
    base = build_compatible_mode_base(workspace_id=workspace_id, region=region)
    return f"{base.rstrip('/')}/chat/completions"


def build_embeddings_url(
    *,
    workspace_id: Optional[str] = None,
    region: DashScopeRegion = "cn-beijing",
) -> str:
    """OpenAI-compatible embeddings URL."""
    base = build_compatible_mode_base(workspace_id=workspace_id, region=region)
    return f"{base.rstrip('/')}/embeddings"


def build_rerank_url_qwen3(
    *,
    workspace_id: Optional[str] = None,
    region: DashScopeRegion = "cn-beijing",
) -> str:
    """qwen3-rerank compatible API URL."""
    base = build_compatible_api_base(workspace_id=workspace_id, region=region)
    return f"{base.rstrip('/')}/reranks"


def build_realtime_ws_base(
    *,
    workspace_id: Optional[str] = None,
    region: DashScopeRegion = "cn-beijing",
) -> str:
    """DashScope realtime WebSocket base (Omni, ASR, TTS). No query string."""
    host = resolve_dashscope_host(workspace_id=workspace_id, region=region)
    return f"wss://{host}/api-ws/v1/realtime"


def build_dashscope_inference_ws_url(
    *,
    workspace_id: Optional[str] = None,
    region: DashScopeRegion = "cn-beijing",
) -> str:
    """MaaS inference WebSocket (Fun-ASR realtime + CosyVoice realtime).

    ``wss://{workspace}.{region}.maas.aliyuncs.com/api-ws/v1/inference``
    """
    host = resolve_dashscope_host(workspace_id=workspace_id, region=region)
    return f"wss://{host}/api-ws/v1/inference"


def resolve_realtime_ws_base(
    *,
    explicit_url: Optional[str],
    workspace_id: Optional[str],
    region: DashScopeRegion,
    legacy_realtime_region: Optional[str] = None,
) -> str:
    """Explicit ``DASHSCOPE_REALTIME_WS_BASE`` wins; else workspace; else legacy."""
    if isinstance(explicit_url, str) and explicit_url.strip():
        cleaned = explicit_url.strip().rstrip("/")
        if cleaned.lower().startswith("wss://"):
            return cleaned
    if _clean_workspace_id(workspace_id):
        return build_realtime_ws_base(workspace_id=workspace_id, region=region)
    region_key = str(legacy_realtime_region or "cn").strip().lower()
    if region_key in ("intl", "international", "sg", "singapore", "ap-southeast-1"):
        return LEGACY_REALTIME_WS_BASE_INTL
    return LEGACY_REALTIME_WS_BASE_CN


def resolve_chat_completions_url(
    *,
    explicit_url: Optional[str],
    workspace_id: Optional[str],
    region: DashScopeRegion,
) -> str:
    """Explicit ``QWEN_API_URL`` wins; else workspace; else legacy Beijing."""
    if isinstance(explicit_url, str) and explicit_url.strip():
        return explicit_url.strip()
    if _clean_workspace_id(workspace_id):
        return build_chat_completions_url(workspace_id=workspace_id, region=region)
    return LEGACY_CHAT_COMPLETIONS_URL


def resolve_api_v1_base(
    *,
    explicit_url: Optional[str],
    workspace_id: Optional[str],
    region: DashScopeRegion,
) -> str:
    """Explicit ``DASHSCOPE_API_URL`` wins; else workspace; else legacy."""
    if isinstance(explicit_url, str) and explicit_url.strip():
        cleaned = explicit_url.strip().rstrip("/")
        return f"{cleaned}/"
    if _clean_workspace_id(workspace_id):
        return build_api_v1_base(workspace_id=workspace_id, region=region)
    return LEGACY_API_V1_BASE


def resolve_compatible_mode_base(
    *,
    explicit_chat_url: Optional[str],
    workspace_id: Optional[str],
    region: DashScopeRegion,
) -> str:
    """Derive compatible-mode base from explicit chat URL or workspace."""
    if isinstance(explicit_chat_url, str) and explicit_chat_url.strip():
        url = explicit_chat_url.strip().rstrip("/")
        suffix = "/chat/completions"
        if url.endswith(suffix):
            return url[: -len(suffix)]
        return url
    if _clean_workspace_id(workspace_id):
        return build_compatible_mode_base(workspace_id=workspace_id, region=region)
    return LEGACY_COMPATIBLE_MODE_BASE


def resolve_compatible_api_base(
    *,
    explicit_api_v1: Optional[str],
    workspace_id: Optional[str],
    region: DashScopeRegion,
) -> str:
    """Derive compatible-api base from explicit api/v1 URL or workspace."""
    if isinstance(explicit_api_v1, str) and explicit_api_v1.strip():
        cleaned = explicit_api_v1.strip().rstrip("/")
        if cleaned.endswith("/api/v1"):
            return cleaned.replace("/api/v1", "/compatible-api/v1")
    if _clean_workspace_id(workspace_id):
        return build_compatible_api_base(workspace_id=workspace_id, region=region)
    return LEGACY_COMPATIBLE_API_BASE


def dashscope_endpoint_summary(
    *,
    explicit_chat_url: Optional[str],
    explicit_api_v1: Optional[str],
    explicit_realtime_ws: Optional[str] = None,
    workspace_id: Optional[str],
    region_raw: Optional[str],
    legacy_realtime_region: Optional[str] = None,
) -> DashScopeEndpointSummary:
    """Startup/debug snapshot of resolved DashScope HTTP endpoints."""
    region = normalize_dashscope_region(region_raw)
    ws = _clean_workspace_id(workspace_id)
    chat = resolve_chat_completions_url(
        explicit_url=explicit_chat_url,
        workspace_id=ws,
        region=region,
    )
    api_v1 = resolve_api_v1_base(
        explicit_url=explicit_api_v1,
        workspace_id=ws,
        region=region,
    )
    compatible = resolve_compatible_mode_base(
        explicit_chat_url=explicit_chat_url,
        workspace_id=ws,
        region=region,
    )
    realtime_ws = resolve_realtime_ws_base(
        explicit_url=explicit_realtime_ws,
        workspace_id=ws,
        region=region,
        legacy_realtime_region=legacy_realtime_region,
    )
    if isinstance(explicit_chat_url, str) and explicit_chat_url.strip():
        mode = "explicit"
    elif ws:
        mode = "workspace"
    else:
        mode = "legacy"
    return {
        "mode": mode,
        "region": region,
        "workspace_id": ws,
        "chat_completions_url": chat,
        "api_v1_base": api_v1,
        "compatible_mode_base": compatible,
        "realtime_ws_base": realtime_ws,
    }
