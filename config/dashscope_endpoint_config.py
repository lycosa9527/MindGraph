"""DashScope HTTP endpoint configuration (workspace MaaS migration).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional

from config.dashscope_urls import (
    DashScopeEndpointSummary,
    DashScopeRegion,
    build_embeddings_url,
    build_rerank_url_qwen3,
    dashscope_endpoint_summary,
    normalize_dashscope_region,
    resolve_api_v1_base,
    resolve_chat_completions_url,
    resolve_compatible_mode_base,
    resolve_realtime_ws_base,
)


class DashScopeEndpointConfigMixin:
    """Workspace-aware DashScope HTTP URL resolution."""

    if TYPE_CHECKING:

        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            return _default

    @property
    def DASHSCOPE_WORKSPACE_ID(self) -> Optional[str]:
        """
        DashScope 业务空间 ID (WorkspaceId).

        When set (and ``QWEN_API_URL`` / ``DASHSCOPE_API_URL`` are unset), HTTP
        endpoints use ``https://{WorkspaceId}.{region}.maas.aliyuncs.com/…``.
        """
        raw = self._get_cached_value("DASHSCOPE_WORKSPACE_ID", "")
        if not isinstance(raw, str):
            return None
        cleaned = raw.strip()
        return cleaned or None

    @property
    def DASHSCOPE_REGION(self) -> DashScopeRegion:
        """
        DashScope region for workspace MaaS hosts.

        Examples: ``cn-beijing``, ``ap-southeast-1``, ``us``, ``eu-central-1``,
        ``ap-northeast-1``. Aliases: ``cn``, ``sg``, ``intl``, ``tokyo``.
        """
        raw = self._get_cached_value("DASHSCOPE_REGION", "cn-beijing")
        return normalize_dashscope_region(str(raw or "cn-beijing"))

    def _dashscope_url_inputs(
        self,
    ) -> tuple[
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[str],
        DashScopeRegion,
        str,
    ]:
        explicit_chat = os.environ.get("QWEN_API_URL")
        explicit_api = os.environ.get("DASHSCOPE_API_URL")
        explicit_realtime = os.environ.get("DASHSCOPE_REALTIME_WS_BASE")
        workspace_id = self.DASHSCOPE_WORKSPACE_ID
        region = normalize_dashscope_region(self.DASHSCOPE_REGION)
        legacy_realtime = str(self._get_cached_value("DASHSCOPE_REALTIME_REGION", "cn") or "cn")
        return explicit_chat, explicit_api, explicit_realtime, workspace_id, region, legacy_realtime

    @property
    def QWEN_API_URL(self) -> str:
        """Get Qwen chat completions URL (legacy, workspace, or explicit env)."""
        explicit_chat, _, _, workspace_id, region, _ = self._dashscope_url_inputs()
        return resolve_chat_completions_url(
            explicit_url=explicit_chat,
            workspace_id=workspace_id,
            region=region,
        )

    @property
    def DASHSCOPE_API_URL(self) -> str:
        """Dashscope native ``/api/v1/`` base (legacy, workspace, or explicit env)."""
        _, explicit_api, _, workspace_id, region, _ = self._dashscope_url_inputs()
        return resolve_api_v1_base(
            explicit_url=explicit_api,
            workspace_id=workspace_id,
            region=region,
        )

    @property
    def DASHSCOPE_COMPATIBLE_MODE_BASE(self) -> str:
        """OpenAI-compatible REST base ``…/compatible-mode/v1``."""
        explicit_chat, _, _, workspace_id, region, _ = self._dashscope_url_inputs()
        return resolve_compatible_mode_base(
            explicit_chat_url=explicit_chat,
            workspace_id=workspace_id,
            region=region,
        )

    @property
    def DASHSCOPE_EMBEDDINGS_URL(self) -> str:
        """OpenAI-compatible embeddings endpoint."""
        explicit_chat, _, _, workspace_id, region, _ = self._dashscope_url_inputs()
        if isinstance(explicit_chat, str) and explicit_chat.strip():
            base = resolve_compatible_mode_base(
                explicit_chat_url=explicit_chat,
                workspace_id=workspace_id,
                region=region,
            )
            return f"{base.rstrip('/')}/embeddings"
        return build_embeddings_url(workspace_id=workspace_id, region=region)

    @property
    def DASHSCOPE_RERANK_URL_QWEN3(self) -> str:
        """qwen3-rerank compatible API endpoint."""
        _, explicit_api, _, workspace_id, region, _ = self._dashscope_url_inputs()
        if isinstance(explicit_api, str) and explicit_api.strip():
            cleaned = explicit_api.strip().rstrip("/")
            if cleaned.endswith("/api/v1"):
                return cleaned.replace("/api/v1", "/compatible-api/v1") + "/reranks"
        return build_rerank_url_qwen3(workspace_id=workspace_id, region=region)

    @property
    def DASHSCOPE_REALTIME_WS_BASE(self) -> str:
        """
        DashScope realtime WebSocket origin (no path/query).

        Override with ``DASHSCOPE_REALTIME_WS_BASE`` (full ``wss://…/realtime`` URL
        without ``?model=``). When ``DASHSCOPE_WORKSPACE_ID`` is set, uses the
        workspace MaaS host; otherwise ``DASHSCOPE_REALTIME_REGION`` selects legacy
        Beijing vs international endpoints.
        """
        _, _, explicit_realtime, workspace_id, region, legacy_realtime = self._dashscope_url_inputs()
        return resolve_realtime_ws_base(
            explicit_url=explicit_realtime,
            workspace_id=workspace_id,
            region=region,
            legacy_realtime_region=legacy_realtime,
        )

    @property
    def DASHSCOPE_ENDPOINT_SUMMARY(self) -> DashScopeEndpointSummary:
        """Resolved HTTP endpoint mode for startup logs."""
        explicit_chat, explicit_api, explicit_realtime, workspace_id, region, legacy_realtime = (
            self._dashscope_url_inputs()
        )
        return dashscope_endpoint_summary(
            explicit_chat_url=explicit_chat,
            explicit_api_v1=explicit_api,
            explicit_realtime_ws=explicit_realtime,
            workspace_id=workspace_id,
            region_raw=region,
            legacy_realtime_region=legacy_realtime,
        )
