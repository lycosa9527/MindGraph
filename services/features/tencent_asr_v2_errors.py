"""Tencent ASR error catalog for Voice Notes.

V2 WebSocket numeric codes:
https://cloud.tencent.com/document/api/1093/131127

HTTP API public + business codes:
https://cloud.tencent.com/document/api/1093/35647

Realtime Voice Notes uses V2 integers. String codes are classified too so a
wrapped ``Error.Code`` or future mixed payload still maps to a stable category.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Browser ``error.code`` values (frontend i18n keys live under auth.voiceNotes.*).
TENCENT_ASR_CATEGORY_AUTH = "tencent_auth"
TENCENT_ASR_CATEGORY_SERVICE = "tencent_service"
TENCENT_ASR_CATEGORY_QUOTA = "tencent_quota"
TENCENT_ASR_CATEGORY_ARREARS = "tencent_arrears"
TENCENT_ASR_CATEGORY_CONCURRENCY = "tencent_concurrency"
TENCENT_ASR_CATEGORY_RPS = "tencent_rps"
TENCENT_ASR_CATEGORY_AUDIO = "tencent_audio"
TENCENT_ASR_CATEGORY_SEND_RATE = "tencent_send_rate"
TENCENT_ASR_CATEGORY_IDLE = "tencent_idle"
TENCENT_ASR_CATEGORY_RETRY = "tencent_retry"
TENCENT_ASR_CATEGORY_REGION = "tencent_region"
TENCENT_ASR_CATEGORY_PARAM = "tencent_param"
TENCENT_ASR_CATEGORY_APPID = "tencent_appid"
TENCENT_ASR_CATEGORY_UPSTREAM = "upstream"

TENCENT_ASR_ERROR_CATEGORIES = frozenset(
    {
        TENCENT_ASR_CATEGORY_AUTH,
        TENCENT_ASR_CATEGORY_SERVICE,
        TENCENT_ASR_CATEGORY_QUOTA,
        TENCENT_ASR_CATEGORY_ARREARS,
        TENCENT_ASR_CATEGORY_CONCURRENCY,
        TENCENT_ASR_CATEGORY_RPS,
        TENCENT_ASR_CATEGORY_AUDIO,
        TENCENT_ASR_CATEGORY_SEND_RATE,
        TENCENT_ASR_CATEGORY_IDLE,
        TENCENT_ASR_CATEGORY_RETRY,
        TENCENT_ASR_CATEGORY_REGION,
        TENCENT_ASR_CATEGORY_PARAM,
        TENCENT_ASR_CATEGORY_APPID,
        TENCENT_ASR_CATEGORY_UPSTREAM,
    }
)

# V2 WebSocket ``code`` integers (131127).
TENCENT_ASR_V2_NUMERIC: dict[int, tuple[str, str]] = {
    4000: (TENCENT_ASR_CATEGORY_SEND_RATE, "Audio was sent faster than realtime"),
    4001: (TENCENT_ASR_CATEGORY_PARAM, "Tencent ASR rejected the session parameters"),
    4002: (TENCENT_ASR_CATEGORY_AUTH, "Tencent ASR authentication failed"),
    4003: (TENCENT_ASR_CATEGORY_SERVICE, "Tencent ASR is not enabled for this AppID"),
    4004: (TENCENT_ASR_CATEGORY_QUOTA, "Tencent ASR resource pack is exhausted"),
    4005: (TENCENT_ASR_CATEGORY_ARREARS, "Tencent Cloud account is in arrears"),
    4006: (TENCENT_ASR_CATEGORY_CONCURRENCY, "Tencent ASR concurrency limit reached"),
    4007: (TENCENT_ASR_CATEGORY_AUDIO, "Tencent ASR could not decode the audio"),
    4008: (TENCENT_ASR_CATEGORY_IDLE, "Tencent ASR idle timeout (no audio for 15s)"),
    4009: (TENCENT_ASR_CATEGORY_UPSTREAM, "Tencent ASR client connection closed"),
    4010: (TENCENT_ASR_CATEGORY_PARAM, "Tencent ASR received an unknown text frame"),
    5000: (
        TENCENT_ASR_CATEGORY_RETRY,
        "Tencent ASR engine overload or network jitter; retry the session",
    ),
    5001: (
        TENCENT_ASR_CATEGORY_RETRY,
        "Tencent ASR engine overload or network jitter; retry the session",
    ),
    5002: (
        TENCENT_ASR_CATEGORY_RETRY,
        "Tencent ASR engine overload or network jitter; retry the session",
    ),
    6001: (TENCENT_ASR_CATEGORY_REGION, "Tencent ASR China endpoint blocked an overseas call"),
}

# Official 说明 from 131127 — backend logs must quote these, not paraphrases.
TENCENT_ASR_V2_OFFICIAL_ZH: dict[int, str] = {
    4000: "音频数据发送过多，请1秒内最多发送3秒音频数据。",
    4001: "参数不合法，具体详情参考 message。",
    4002: "鉴权失败。",
    4003: "AppID 服务未开通，请在控制台开通服务。",
    4004: "资源包耗尽，请开通后付费或者购买资源包。",
    4005: "账户欠费停止服务，请及时充值。",
    4006: "账号当前调用并发超限。",
    4007: "音频解码失败，请检查上传音频数据格式是否与调用参数一致。",
    4008: "客户端超过15秒未发送音频数据。",
    4009: "客户端连接断开。",
    4010: "客户端上传未知文本消息。",
    5000: "因机器负载过高、网络抖动等导致失败，请重新发起识别。",
    5001: "因机器负载过高、网络抖动等导致失败，请重新发起识别。",
    5002: "因机器负载过高、网络抖动等导致失败，请重新发起识别。",
    6001: "境外调用请前往腾讯云国际站开通服务。国内站用户请检查是否使用境外代理，如果使用请关闭。",
}

# Local transport miss (no V2 JSON). Official equivalent is 5000 网络抖动.
TENCENT_ASR_NO_V2_FRAME = "no_v2_frame"
TENCENT_ASR_TRANSIENT_EQUIVALENT = 5000

# Every public + business code on 35647 → category.
TENCENT_ASR_API_STRING: dict[str, str] = {
    "ActionOffline": TENCENT_ASR_CATEGORY_PARAM,
    "AuthFailure": TENCENT_ASR_CATEGORY_AUTH,
    "AuthFailure.CheckResourceResponseCodeError": TENCENT_ASR_CATEGORY_AUTH,
    "AuthFailure.InvalidAuthorization": TENCENT_ASR_CATEGORY_AUTH,
    "AuthFailure.InvalidSecretId": TENCENT_ASR_CATEGORY_AUTH,
    "AuthFailure.MFAFailure": TENCENT_ASR_CATEGORY_AUTH,
    "AuthFailure.SecretIdNotFound": TENCENT_ASR_CATEGORY_AUTH,
    "AuthFailure.SignatureExpire": TENCENT_ASR_CATEGORY_AUTH,
    "AuthFailure.SignatureFailure": TENCENT_ASR_CATEGORY_AUTH,
    "AuthFailure.TokenFailure": TENCENT_ASR_CATEGORY_AUTH,
    "AuthFailure.UnauthorizedOperation": TENCENT_ASR_CATEGORY_AUTH,
    "DryRunOperation": TENCENT_ASR_CATEGORY_PARAM,
    "FailedOperation": TENCENT_ASR_CATEGORY_RETRY,
    "FailedOperation.CheckAuthInfoFailed": TENCENT_ASR_CATEGORY_AUTH,
    "FailedOperation.ErrorDownFile": TENCENT_ASR_CATEGORY_RETRY,
    "FailedOperation.ErrorRecognize": TENCENT_ASR_CATEGORY_RETRY,
    "FailedOperation.NoSuchTask": TENCENT_ASR_CATEGORY_PARAM,
    "FailedOperation.NotExistentVoicePrintId": TENCENT_ASR_CATEGORY_PARAM,
    "FailedOperation.ServiceIsolate": TENCENT_ASR_CATEGORY_ARREARS,
    "FailedOperation.UserHasNoAmount": TENCENT_ASR_CATEGORY_QUOTA,
    "FailedOperation.UserHasNoFreeAmount": TENCENT_ASR_CATEGORY_QUOTA,
    "FailedOperation.UserNotRegistered": TENCENT_ASR_CATEGORY_SERVICE,
    "InternalError": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.ErrorConfigure": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.ErrorCreateLog": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.ErrorDownFile": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.ErrorFailNewprequest": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.ErrorFailWritetodb": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.ErrorFileCannotopen": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.ErrorGetRoute": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.ErrorMakeLogpath": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.ErrorRecognize": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.FailAccessDatabase": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.FailAccessRedis": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.FailedVoicePrintDecode": TENCENT_ASR_CATEGORY_AUDIO,
    "InternalError.FailedVoicePrintEnroll": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.FailedVoicePrintVerify": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.TagRequestError": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.VoicePrintAudioFailed": TENCENT_ASR_CATEGORY_AUDIO,
    "InternalError.VoicePrintDecodeFailed": TENCENT_ASR_CATEGORY_AUDIO,
    "InternalError.VoicePrintEnrollFailed": TENCENT_ASR_CATEGORY_RETRY,
    "InternalError.VoicePrintVerifyFailed": TENCENT_ASR_CATEGORY_RETRY,
    "InvalidAction": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameter": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameter.ErrorContentlength": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameter.ErrorParamsMissing": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameter.ErrorParsequest": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameter.FailedVoicePrintDecode": TENCENT_ASR_CATEGORY_AUDIO,
    "InvalidParameter.FileEncode": TENCENT_ASR_CATEGORY_AUDIO,
    "InvalidParameter.InvalidParameter": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameter.InvalidVocabState": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameter.KeyWordLibNameExist": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameter.ModelState": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.ErrorInvalidAppid": TENCENT_ASR_CATEGORY_APPID,
    "InvalidParameterValue.ErrorInvalidClientip": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.ErrorInvalidEngservice": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.ErrorInvalidProjectid": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.ErrorInvalidRequestid": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.ErrorInvalidSourcetype": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.ErrorInvalidSubservicetype": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.ErrorInvalidUrl": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.ErrorInvalidUseraudiokey": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.ErrorInvalidVoiceFormat": TENCENT_ASR_CATEGORY_AUDIO,
    "InvalidParameterValue.ErrorInvalidVoicedata": TENCENT_ASR_CATEGORY_AUDIO,
    "InvalidParameterValue.ErrorVoicedataTooLong": TENCENT_ASR_CATEGORY_AUDIO,
    "InvalidParameterValue.InvalidParameterLength": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.InvalidVocabId": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.InvalidVocabState": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.InvalidWordWeight": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.InvalidWordWeightStr": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.ModelId": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidParameterValue.NoHumanVoice": TENCENT_ASR_CATEGORY_AUDIO,
    "InvalidParameterValue.ToState": TENCENT_ASR_CATEGORY_PARAM,
    "InvalidRequest": TENCENT_ASR_CATEGORY_PARAM,
    "IpInBlacklist": TENCENT_ASR_CATEGORY_REGION,
    "IpNotInWhitelist": TENCENT_ASR_CATEGORY_REGION,
    "LimitExceeded": TENCENT_ASR_CATEGORY_CONCURRENCY,
    "LimitExceeded.CustomizationFull": TENCENT_ASR_CATEGORY_CONCURRENCY,
    "LimitExceeded.OnlineFull": TENCENT_ASR_CATEGORY_CONCURRENCY,
    "LimitExceeded.VocabFull": TENCENT_ASR_CATEGORY_CONCURRENCY,
    "LimitExceeded.VoicePrintFull": TENCENT_ASR_CATEGORY_CONCURRENCY,
    "MissingParameter": TENCENT_ASR_CATEGORY_PARAM,
    "NoSuchProduct": TENCENT_ASR_CATEGORY_PARAM,
    "NoSuchVersion": TENCENT_ASR_CATEGORY_PARAM,
    "RequestLimitExceeded": TENCENT_ASR_CATEGORY_RPS,
    "RequestLimitExceeded.GlobalRegionUinLimitExceeded": TENCENT_ASR_CATEGORY_RPS,
    "RequestLimitExceeded.IPLimitExceeded": TENCENT_ASR_CATEGORY_RPS,
    "RequestLimitExceeded.UinLimitExceeded": TENCENT_ASR_CATEGORY_RPS,
    "RequestSizeLimitExceeded": TENCENT_ASR_CATEGORY_PARAM,
    "ResourceInUse": TENCENT_ASR_CATEGORY_RETRY,
    "ResourceInsufficient": TENCENT_ASR_CATEGORY_RETRY,
    "ResourceNotFound": TENCENT_ASR_CATEGORY_PARAM,
    "ResourceUnavailable": TENCENT_ASR_CATEGORY_RETRY,
    "ResponseSizeLimitExceeded": TENCENT_ASR_CATEGORY_RETRY,
    "ServiceUnavailable": TENCENT_ASR_CATEGORY_RETRY,
    "UnauthorizedOperation": TENCENT_ASR_CATEGORY_AUTH,
    "UnknownParameter": TENCENT_ASR_CATEGORY_PARAM,
    "UnsupportedOperation": TENCENT_ASR_CATEGORY_PARAM,
    "UnsupportedProtocol": TENCENT_ASR_CATEGORY_PARAM,
    "UnsupportedRegion": TENCENT_ASR_CATEGORY_REGION,
}

_STRING_PREFIX_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("AuthFailure", TENCENT_ASR_CATEGORY_AUTH),
    ("UnauthorizedOperation", TENCENT_ASR_CATEGORY_AUTH),
    ("FailedOperation.UserNotRegistered", TENCENT_ASR_CATEGORY_SERVICE),
    ("FailedOperation.UserHasNo", TENCENT_ASR_CATEGORY_QUOTA),
    ("FailedOperation.ServiceIsolate", TENCENT_ASR_CATEGORY_ARREARS),
    ("FailedOperation.CheckAuthInfoFailed", TENCENT_ASR_CATEGORY_AUTH),
    ("RequestLimitExceeded", TENCENT_ASR_CATEGORY_RPS),
    ("LimitExceeded", TENCENT_ASR_CATEGORY_CONCURRENCY),
    ("InvalidParameterValue.ErrorInvalidAppid", TENCENT_ASR_CATEGORY_APPID),
    ("InvalidParameterValue.ErrorInvalidVoice", TENCENT_ASR_CATEGORY_AUDIO),
    ("InvalidParameterValue.ErrorVoicedata", TENCENT_ASR_CATEGORY_AUDIO),
    ("InvalidParameterValue.NoHumanVoice", TENCENT_ASR_CATEGORY_AUDIO),
    ("InvalidParameter.FailedVoicePrintDecode", TENCENT_ASR_CATEGORY_AUDIO),
    ("InvalidParameter.FileEncode", TENCENT_ASR_CATEGORY_AUDIO),
    ("InvalidParameter", TENCENT_ASR_CATEGORY_PARAM),
    ("MissingParameter", TENCENT_ASR_CATEGORY_PARAM),
    ("UnknownParameter", TENCENT_ASR_CATEGORY_PARAM),
    ("InternalError.VoicePrint", TENCENT_ASR_CATEGORY_AUDIO),
    ("InternalError.FailedVoicePrintDecode", TENCENT_ASR_CATEGORY_AUDIO),
    ("InternalError", TENCENT_ASR_CATEGORY_RETRY),
    ("ServiceUnavailable", TENCENT_ASR_CATEGORY_RETRY),
    ("FailedOperation.ErrorRecognize", TENCENT_ASR_CATEGORY_RETRY),
    ("UnsupportedRegion", TENCENT_ASR_CATEGORY_REGION),
    ("FailedOperation", TENCENT_ASR_CATEGORY_RETRY),
)

_CATEGORY_FALLBACK_MESSAGE: dict[str, str] = {
    TENCENT_ASR_CATEGORY_AUTH: "Tencent ASR authentication failed",
    TENCENT_ASR_CATEGORY_SERVICE: "Tencent ASR is not enabled for this AppID",
    TENCENT_ASR_CATEGORY_QUOTA: "Tencent ASR resource pack is exhausted",
    TENCENT_ASR_CATEGORY_ARREARS: "Tencent Cloud account is in arrears",
    TENCENT_ASR_CATEGORY_CONCURRENCY: "Tencent ASR concurrency limit reached",
    TENCENT_ASR_CATEGORY_RPS: "Tencent ASR request rate limit reached",
    TENCENT_ASR_CATEGORY_AUDIO: "Tencent ASR could not decode the audio",
    TENCENT_ASR_CATEGORY_SEND_RATE: "Audio was sent faster than realtime",
    TENCENT_ASR_CATEGORY_IDLE: "Tencent ASR idle timeout (no audio for 15s)",
    TENCENT_ASR_CATEGORY_RETRY: ("Tencent ASR engine overload or network jitter; retry the session"),
    TENCENT_ASR_CATEGORY_REGION: "Tencent ASR China endpoint blocked an overseas call",
    TENCENT_ASR_CATEGORY_PARAM: "Tencent ASR rejected the session parameters",
    TENCENT_ASR_CATEGORY_APPID: "Tencent Cloud AppID is invalid",
    TENCENT_ASR_CATEGORY_UPSTREAM: "Tencent ASR upstream error",
}


@dataclass(frozen=True)
class TencentAsrClassifiedError:
    """Stable browser category plus provider identity."""

    category: str
    message: str
    provider_code: str


class TencentAsrHandshakeError(RuntimeError):
    """Connect or V2 handshake failed before recognition started."""

    def __init__(self, classified: TencentAsrClassifiedError) -> None:
        super().__init__(classified.message)
        self.classified = classified


def tencent_asr_connect_error(message: str) -> TencentAsrClassifiedError:
    """No V2 frame (TCP/handshake timeout). Official equivalent: 5000."""
    text = (message or "").strip() or "Tencent ASR opening handshake timed out"
    return TencentAsrClassifiedError(
        category=TENCENT_ASR_CATEGORY_RETRY,
        message=text,
        provider_code=TENCENT_ASR_NO_V2_FRAME,
    )


def _v2_numeric_code(provider_code: str) -> Optional[int]:
    raw = provider_code.strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    return None


def format_tencent_asr_v2_log(
    classified: TencentAsrClassifiedError,
    *,
    voice_id: str = "",
    phase: str = "",
) -> str:
    """One log line: official V2 code + 131127 说明, then our category and payload."""
    numeric = _v2_numeric_code(classified.provider_code)
    official = ""
    if numeric is not None:
        code_field = f"code={numeric}"
        official = TENCENT_ASR_V2_OFFICIAL_ZH.get(numeric, "")
    elif classified.provider_code == TENCENT_ASR_NO_V2_FRAME:
        code_field = f"code=- equivalent={TENCENT_ASR_TRANSIENT_EQUIVALENT}"
        official = TENCENT_ASR_V2_OFFICIAL_ZH[TENCENT_ASR_TRANSIENT_EQUIVALENT]
    else:
        code_field = f"code={classified.provider_code or '-'}"
    parts = ["Tencent ASR V2", code_field]
    if official:
        parts.append(f"official={official}")
    parts.append(f"category={classified.category}")
    if phase:
        parts.append(f"phase={phase}")
    if voice_id:
        parts.append(f"voice_id={voice_id}")
    if classified.message:
        parts.append(f"message={classified.message}")
    return " ".join(parts)


def tencent_asr_upstream_error(message: str) -> TencentAsrClassifiedError:
    """Provider disconnect / non-catalog failure."""
    text = (message or "").strip() or _CATEGORY_FALLBACK_MESSAGE[TENCENT_ASR_CATEGORY_UPSTREAM]
    return TencentAsrClassifiedError(
        category=TENCENT_ASR_CATEGORY_UPSTREAM,
        message=text,
        provider_code="",
    )


def _nested_error_block(payload: dict[str, Any]) -> dict[str, Any]:
    raw_error = payload.get("Error")
    if isinstance(raw_error, dict):
        return raw_error
    raw_response = payload.get("Response")
    if isinstance(raw_response, dict):
        nested = raw_response.get("Error")
        if isinstance(nested, dict):
            return nested
    raw_inner = payload.get("error")
    if isinstance(raw_inner, dict):
        return raw_inner
    return {}


def _provider_string(payload: dict[str, Any], nested: dict[str, Any]) -> str:
    for raw in (
        payload.get("error_code"),
        nested.get("Code"),
        nested.get("code"),
        payload.get("code"),
    ):
        if isinstance(raw, str) and raw.strip() and not raw.strip().lstrip("-").isdigit():
            return raw.strip()
    return ""


def _provider_int(payload: dict[str, Any], nested: dict[str, Any]) -> Optional[int]:
    for raw in (payload.get("code"), nested.get("Code"), nested.get("code")):
        if isinstance(raw, bool):
            continue
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
            return int(raw.strip())
    return None


def _provider_message(payload: dict[str, Any], nested: dict[str, Any]) -> str:
    for raw in (payload.get("message"), nested.get("Message"), nested.get("message")):
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _category_for_string(code: str) -> Optional[str]:
    exact = TENCENT_ASR_API_STRING.get(code)
    if exact:
        return exact
    for prefix, category in _STRING_PREFIX_CATEGORIES:
        if code == prefix or code.startswith(f"{prefix}."):
            return category
    return None


def _category_for_unknown_int(code: int) -> str:
    if 5000 <= code <= 5999:
        return TENCENT_ASR_CATEGORY_RETRY
    if 4000 <= code <= 4999:
        return TENCENT_ASR_CATEGORY_PARAM
    return TENCENT_ASR_CATEGORY_UPSTREAM


def classify_tencent_asr_error(payload: dict[str, Any]) -> TencentAsrClassifiedError:
    """Map a V2 or 35647 payload to a stable Voice Notes error."""
    nested = _nested_error_block(payload)
    numeric = _provider_int(payload, nested)
    string_code = _provider_string(payload, nested)
    provider_message = _provider_message(payload, nested)

    category: Optional[str] = None
    default_message = ""
    provider_code = ""

    if numeric is not None and numeric in TENCENT_ASR_V2_NUMERIC:
        category, default_message = TENCENT_ASR_V2_NUMERIC[numeric]
        provider_code = str(numeric)
    elif string_code:
        category = _category_for_string(string_code)
        provider_code = string_code
    elif numeric is not None and numeric != 0:
        category = _category_for_unknown_int(numeric)
        provider_code = str(numeric)

    if category is None:
        category = TENCENT_ASR_CATEGORY_UPSTREAM
    if category not in TENCENT_ASR_ERROR_CATEGORIES:
        category = TENCENT_ASR_CATEGORY_UPSTREAM
    if not default_message:
        default_message = _CATEGORY_FALLBACK_MESSAGE[category]
    message = provider_message or default_message
    return TencentAsrClassifiedError(
        category=category,
        message=message,
        provider_code=provider_code,
    )


def browser_error_payload(classified: TencentAsrClassifiedError) -> dict[str, str]:
    """JSON fields for the Voice Notes browser socket."""
    return {
        "type": "error",
        "code": classified.category,
        "message": classified.message,
        "provider_code": classified.provider_code,
    }
