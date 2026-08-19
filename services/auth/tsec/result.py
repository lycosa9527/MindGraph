"""Parse and audit-log DescribeCaptchaResult output fields (API 36926)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from services.auth.tsec.config import tencent_captcha_app_id

logger = logging.getLogger(__name__)

_TICKET_PREFIX_LEN = 20
_ABUSE_REASONS = frozenset(
    {
        "evil_level",
        "ticket_diff",
        "randstr_mismatch",
        "ticket_reused",
        "decrypt_fail",
    }
)
_CONFIG_REASONS = frozenset({"appid_ticket_mismatch", "appid_secretkey_mismatch"})
_CLIENT_REASONS = frozenset({"disaster_ticket", "missing_ticket"})
_DISASTER_PREFIXES = ("trerror_", "terror_")


@dataclass(frozen=True)
class TsecVerifyTrace:
    """Optional frontend callback fields for audit correlation."""

    sid: Optional[str] = None
    verify_duration: Optional[int] = None
    action_duration: Optional[int] = None


@dataclass(frozen=True)
class TsecDescribeResult:
    """All DescribeCaptchaResult output parameters from the Cloud API."""

    captcha_code: Optional[int]
    captcha_msg: Optional[str]
    evil_level: Optional[int]
    get_captcha_time: Optional[int]
    evil_bitmap: Optional[int]
    submit_captcha_time: Optional[int]
    device_risk_category: Optional[str]
    score: Optional[int]
    request_id: Optional[str]
    code_parse_error: bool = False


def audit_kind(outcome: str, reason: str) -> str:
    """Classify an attempt for grep: pass, abuse, client, config, provider, replay."""
    if outcome == "pass":
        return "pass"
    if reason in _ABUSE_REASONS:
        return "abuse"
    if reason in _CONFIG_REASONS:
        return "config"
    if reason in _CLIENT_REASONS:
        return "client"
    if reason == "ticket_expired":
        return "replay"
    if reason.startswith("cloud_api_") or reason == "provider_error":
        return "provider"
    return "reject"


def parse_disaster_ticket(ticket: str) -> tuple[Optional[str], Optional[str]]:
    """Parse ``trerror_{errorCode}_{CaptchaAppId}_{unix}`` from the PDF."""
    clean = (ticket or "").strip()
    if not clean.startswith(_DISASTER_PREFIXES):
        return None, None
    parts = clean.split("_")
    if len(parts) < 4:
        return None, None
    return parts[1] or None, parts[2] or None


def ticket_prefix(ticket: str) -> str:
    """Short ticket stem for logs (never the full ticket)."""
    clean = (ticket or "").strip()
    if len(clean) <= _TICKET_PREFIX_LEN:
        return clean
    return f"{clean[:_TICKET_PREFIX_LEN]}..."


def _optional_int(value: Any) -> Optional[int]:
    """Parse an optional integer Cloud API field."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_describe_response(resp: dict[str, Any]) -> TsecDescribeResult:
    """Read every documented output field from a DescribeCaptchaResult Response."""
    raw_code = resp.get("CaptchaCode")
    code_parse_error = False
    captcha_code: Optional[int]
    if raw_code is None:
        captcha_code = None
    else:
        try:
            captcha_code = int(raw_code)
        except (TypeError, ValueError):
            captcha_code = None
            code_parse_error = True
    raw_risk = resp.get("DeviceRiskCategory")
    risk = str(raw_risk).strip() if raw_risk is not None and str(raw_risk).strip() else None
    raw_msg = resp.get("CaptchaMsg")
    captcha_msg = str(raw_msg) if raw_msg is not None else None
    raw_request = resp.get("RequestId")
    request_id = str(raw_request) if raw_request else None
    return TsecDescribeResult(
        captcha_code=captcha_code,
        captcha_msg=captcha_msg,
        evil_level=_optional_int(resp.get("EvilLevel")),
        get_captcha_time=_optional_int(resp.get("GetCaptchaTime")),
        evil_bitmap=_optional_int(resp.get("EvilBitmap")),
        submit_captcha_time=_optional_int(resp.get("SubmitCaptchaTime")),
        device_risk_category=risk,
        score=_optional_int(resp.get("Score")),
        request_id=request_id,
        code_parse_error=code_parse_error,
    )


def log_tsec_audit(
    outcome: str,
    reason: str,
    user_ip: str,
    ticket: str,
    parsed: Optional[TsecDescribeResult] = None,
    trace: Optional[TsecVerifyTrace] = None,
    client_error: Optional[str] = None,
) -> None:
    """Emit one [TsecAudit] line with every useful T-Sec field."""
    frontend_error, disaster_app_id = parse_disaster_ticket(ticket)
    app_id = disaster_app_id or tencent_captcha_app_id() or None
    parts = [
        f"outcome={outcome}",
        f"kind={audit_kind(outcome, reason)}",
        f"reason={reason}",
        f"ip={user_ip}",
        f"app_id={app_id}",
        f"ticket={ticket_prefix(ticket)}",
    ]
    if frontend_error:
        parts.append(f"frontend_error={frontend_error}")
    if client_error:
        parts.append(f"client_error={client_error}")
    if parsed is not None:
        parts.extend(
            [
                f"captcha_code={parsed.captcha_code}",
                f"captcha_msg={parsed.captcha_msg}",
                f"evil_level={parsed.evil_level}",
                f"evil_bitmap={parsed.evil_bitmap}",
                f"score={parsed.score}",
                f"device_risk={parsed.device_risk_category}",
                f"get_time={parsed.get_captcha_time}",
                f"submit_time={parsed.submit_captcha_time}",
                f"request_id={parsed.request_id}",
            ]
        )
    if trace is not None:
        if trace.sid:
            parts.append(f"sid={trace.sid}")
        if trace.verify_duration is not None:
            parts.append(f"verify_ms={trace.verify_duration}")
        if trace.action_duration is not None:
            parts.append(f"action_ms={trace.action_duration}")
    line = "[TsecAudit] " + " ".join(parts)
    if outcome == "pass":
        logger.info(line)
        return
    logger.warning(line)
