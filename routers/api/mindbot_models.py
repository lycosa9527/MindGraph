"""Pydantic request/response models for MindBot admin and callback endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class MindbotConfigPayload(BaseModel):
    """Admin create/update body."""

    dingtalk_robot_code: str = Field(..., min_length=1, max_length=128)
    dingtalk_app_secret: Optional[str] = Field(
        None,
        description="Omit or empty on update to keep existing secret",
    )
    dingtalk_client_id: Optional[str] = Field(None, max_length=128)
    dify_api_base_url: str = Field(..., min_length=1, max_length=512)
    dify_api_key: Optional[str] = Field(
        None,
        description="Omit or empty on update to keep existing key",
    )
    dify_timeout_seconds: int = Field(300, ge=5, le=600)
    dify_inputs_json: Optional[str] = Field(
        None,
        description="Optional JSON object string passed as Dify chat-messages inputs",
    )
    dingtalk_event_token: Optional[str] = Field(
        None,
        max_length=128,
        description="DingTalk event subscription Token; omit on update to keep",
    )
    dingtalk_event_aes_key: Optional[str] = Field(
        None,
        max_length=128,
        description="EncodingAESKey; omit on update to keep",
    )
    dingtalk_event_owner_key: Optional[str] = Field(
        None,
        max_length=128,
        description="appKey, corpId, or suiteKey per DingTalk app type",
    )
    is_enabled: bool = True
    show_chain_of_thought_oto: bool = False
    show_chain_of_thought_internal_group: bool = False
    show_chain_of_thought_cross_org_group: bool = False
    chain_of_thought_max_chars: int = Field(4000, ge=0, le=32000)
    dingtalk_ai_card_template_id: Optional[str] = Field(
        None,
        max_length=128,
        description="Optional AI card template id; empty keeps legacy session webhook / OpenAPI text",
    )
    dingtalk_ai_card_param_key: Optional[str] = Field(
        None,
        max_length=128,
        description="Template variable key for streaming markdown body; empty defaults to 'content'",
    )


class MindbotConfigResponse(BaseModel):
    id: int
    organization_id: int
    public_callback_token: str
    dingtalk_robot_code: str
    dingtalk_app_secret_masked: str
    dify_api_key_masked: str
    dingtalk_client_id: Optional[str]
    dingtalk_event_token_set: bool
    dingtalk_event_aes_key_set: bool
    dingtalk_event_owner_key: Optional[str]
    dify_api_base_url: str
    dify_timeout_seconds: int
    dify_inputs_json: Optional[str]
    show_chain_of_thought_oto: bool
    show_chain_of_thought_internal_group: bool
    show_chain_of_thought_cross_org_group: bool
    chain_of_thought_max_chars: int
    dingtalk_ai_card_template_id: Optional[str]
    dingtalk_ai_card_param_key: Optional[str]
    is_enabled: bool


class DifyServiceStatusResponse(BaseModel):
    """MindBot admin: Dify app API reachability (server-side probe only)."""

    online: bool
    http_status: Optional[int] = None
    error: Optional[str] = None
    probe_url: Optional[str] = Field(
        default=None,
        description="GET target used for the check (no credentials)",
    )


class MindbotMemoryFootprintResponse(BaseModel):
    """In-process MindBot structures for capacity / leak diagnostics (per worker)."""

    oauth_lock_map_size: int = Field(
        ...,
        description="Current entries in the OAuth thundering-herd lock LRU map.",
    )
    oauth_lock_map_max: int = Field(
        ...,
        description="Configured cap before LRU eviction (MINDBOT_OAUTH_LOCK_MAP_MAX).",
    )
    dingtalk_stream_registered_clients: int = Field(
        ...,
        description="DingTalk Stream SDK clients in this process (one per client_id).",
    )
    callback_metrics: dict[str, Any] = Field(
        ...,
        description=(
            "Callback outcome counters since process start. "
            "School managers only receive their organization's ``by_organization_id`` "
            "entry; global aggregates and ``by_robot_code`` are admin-only."
        ),
    )


class DingtalkAiCardStreamingStatusResponse(BaseModel):
    """MindBot admin: probe DingTalk AI card streaming update API (OpenAPI)."""

    ok: bool
    http_status: Optional[int] = None
    error: Optional[str] = Field(
        default=None,
        description="Internal reason token when the probe fails before a DingTalk call.",
    )
    dingtalk_code: Optional[str] = None
    dingtalk_message: Optional[str] = None
    friendly_message: Optional[str] = Field(
        default=None,
        description="Operator-facing summary (mapped from DingTalk or internal reasons).",
    )
    probe_path: str = Field(
        default="/v1.0/card/streaming",
        description="PUT path used (see DingTalk AI card streaming update API).",
    )


class MindbotUsageEventItem(BaseModel):
    """One analytics row for admin (no message body stored)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    mindbot_config_id: Optional[int]
    dingtalk_staff_id: str
    sender_nick: Optional[str]
    dingtalk_sender_id: Optional[str]
    dify_user_key: str
    msg_id: Optional[str]
    dingtalk_conversation_id: Optional[str]
    dify_conversation_id: Optional[str]
    error_code: str
    streaming: bool
    prompt_chars: int
    reply_chars: int
    duration_seconds: Optional[float]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    dingtalk_chat_scope: Optional[str]
    inbound_msg_type: Optional[str]
    conversation_user_turn: Optional[int]
    linked_user_id: Optional[int]
    created_at: datetime
