"""Map DingTalk OpenAPI card error ``code`` values to short operator-facing messages.

Official references:
- Streaming update: https://open.dingtalk.com/document/development/api-streamingupdate
- Create and deliver: Apifox / DingTalk ``card_1.0#CreateAndDeliver`` error tables.
"""

from __future__ import annotations

from typing import Optional

# Streaming update (PUT /v1.0/card/streaming)
_STREAMING_FRIENDLY: dict[str, str] = {
    "param.stream.keyEmpty": "Streaming update: template variable key is empty.",
    "param.stream.contentEmpty": "Streaming update: content is empty.",
    "param.stream.guidEmpty": "Streaming update: guid is empty (required for idempotency).",
    "param.stream.outTrackId": "Streaming update: card instance not found (check outTrackId).",
    "param.stream.isFull": "Streaming update: isFull is missing or invalid (markdown requires true).",
    "param.stream.content": "Streaming update: content too large (per-frame limit).",
}

# Create and deliver (POST /v1.0/card/instances/createAndDeliver)
_CREATE_FRIENDLY: dict[str, str] = {
    "param.cardTemplateIdEmpty": "Create card: template id is empty.",
    "param.templateNotExist": "Create card: template does not exist.",
    "param.templateUnpublished": "Create card: template is not published.",
    "param.cardAlreadyExist": "Create card: outTrackId already used; use a new id.",
    "param.contentUnsafe": "Create card: content failed security review.",
    "param.openSpaceIdInvalid": "Create card: openSpaceId is invalid.",
    "param.openSpaceIdEmpty": "Create card: openSpaceId is empty.",
    "param.openDeliverModelError": (
        "Create card: deliver model invalid (e.g. group chat may need AppKey as "
        "robotCode in imGroupOpenDeliverModel; try MINDBOT_AI_CARD_GROUP_USE_ROBOT_CODE)."
    ),
    "param.userIdEmpty": "Create card: userId (creator) is empty.",
    "param.userIdNotExist": "Create card: userId does not exist.",
    "param.cardPublicDataEmpty": "Create card: card public data is empty.",
}


INTERNAL_PREFLIGHT: dict[str, str] = {
    "no_token": "Could not obtain DingTalk access token.",
    "no_sender_staff": "DingTalk callback is missing sender staff id.",
    "no_conversation_id": "DingTalk group callback is missing conversation id.",
    "network_error": "Network error calling DingTalk API.",
    "empty_body": "Empty or invalid JSON response from DingTalk.",
    "openapi_disabled": "MindBot DingTalk OpenAPI is disabled.",
    "template_not_configured": "AI card template id is not set.",
    "client_id_required": "DingTalk client id (app key) is required.",
    "token_failed": "Could not obtain DingTalk access token.",
}


def describe_ai_card_failure(
    dingtalk_code: Optional[str],
    detail: Optional[str],
) -> str:
    """
    Human-readable line for logs and admin UI.

    ``detail`` is either a DingTalk ``message`` or an internal key from
    ``INTERNAL_PREFLIGHT``.
    """
    c = (dingtalk_code or "").strip()
    d = (detail or "").strip()
    if not c and d:
        if d in INTERNAL_PREFLIGHT:
            return INTERNAL_PREFLIGHT[d]
        if d.startswith("http_"):
            return f"DingTalk returned HTTP error ({d})."
        return d[:400]
    return friendly_dingtalk_card_error(c, d)


def friendly_dingtalk_card_error(code: str, message: str) -> str:
    """
    Return a short English message for logs and admin UI.

    Falls back to ``code`` and DingTalk ``message`` when unknown.
    """
    c = (code or "").strip()
    m = (message or "").strip()
    if c in _STREAMING_FRIENDLY:
        return _STREAMING_FRIENDLY[c]
    if c in _CREATE_FRIENDLY:
        return _CREATE_FRIENDLY[c]
    if c and m:
        return f"{c}: {m}"[:400]
    if c:
        return c[:400]
    if m:
        return m[:400]
    return "DingTalk card API returned an error."
