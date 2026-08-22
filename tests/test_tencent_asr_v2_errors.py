"""Tencent ASR error catalog covers V2 integers and 35647 string codes."""

from __future__ import annotations

from services.features.tencent_asr_v2_errors import (
    TENCENT_ASR_API_STRING,
    TENCENT_ASR_ERROR_CATEGORIES,
    TENCENT_ASR_NO_V2_FRAME,
    TENCENT_ASR_V2_NUMERIC,
    TENCENT_ASR_V2_OFFICIAL_ZH,
    TENCENT_ASR_CATEGORY_APPID,
    TENCENT_ASR_CATEGORY_ARREARS,
    TENCENT_ASR_CATEGORY_AUTH,
    TENCENT_ASR_CATEGORY_QUOTA,
    TENCENT_ASR_CATEGORY_RPS,
    TENCENT_ASR_CATEGORY_RETRY,
    TENCENT_ASR_CATEGORY_SERVICE,
    TENCENT_ASR_CATEGORY_UPSTREAM,
    browser_error_payload,
    classify_tencent_asr_error,
    format_tencent_asr_v2_log,
    tencent_asr_connect_error,
)

# https://cloud.tencent.com/document/api/1093/131127
OFFICIAL_V2_NUMERIC = frozenset(
    {4000, 4001, 4002, 4003, 4004, 4005, 4006, 4007, 4008, 4009, 4010, 5000, 5001, 5002, 6001}
)

# https://cloud.tencent.com/document/api/1093/35647 — public + business.
OFFICIAL_35647_CODES = frozenset(
    {
        "ActionOffline",
        "AuthFailure",
        "AuthFailure.CheckResourceResponseCodeError",
        "AuthFailure.InvalidAuthorization",
        "AuthFailure.InvalidSecretId",
        "AuthFailure.MFAFailure",
        "AuthFailure.SecretIdNotFound",
        "AuthFailure.SignatureExpire",
        "AuthFailure.SignatureFailure",
        "AuthFailure.TokenFailure",
        "AuthFailure.UnauthorizedOperation",
        "DryRunOperation",
        "FailedOperation",
        "FailedOperation.CheckAuthInfoFailed",
        "FailedOperation.ErrorDownFile",
        "FailedOperation.ErrorRecognize",
        "FailedOperation.NoSuchTask",
        "FailedOperation.NotExistentVoicePrintId",
        "FailedOperation.ServiceIsolate",
        "FailedOperation.UserHasNoAmount",
        "FailedOperation.UserHasNoFreeAmount",
        "FailedOperation.UserNotRegistered",
        "InternalError",
        "InternalError.ErrorConfigure",
        "InternalError.ErrorCreateLog",
        "InternalError.ErrorDownFile",
        "InternalError.ErrorFailNewprequest",
        "InternalError.ErrorFailWritetodb",
        "InternalError.ErrorFileCannotopen",
        "InternalError.ErrorGetRoute",
        "InternalError.ErrorMakeLogpath",
        "InternalError.ErrorRecognize",
        "InternalError.FailAccessDatabase",
        "InternalError.FailAccessRedis",
        "InternalError.FailedVoicePrintDecode",
        "InternalError.FailedVoicePrintEnroll",
        "InternalError.FailedVoicePrintVerify",
        "InternalError.TagRequestError",
        "InternalError.VoicePrintAudioFailed",
        "InternalError.VoicePrintDecodeFailed",
        "InternalError.VoicePrintEnrollFailed",
        "InternalError.VoicePrintVerifyFailed",
        "InvalidAction",
        "InvalidParameter",
        "InvalidParameter.ErrorContentlength",
        "InvalidParameter.ErrorParamsMissing",
        "InvalidParameter.ErrorParsequest",
        "InvalidParameter.FailedVoicePrintDecode",
        "InvalidParameter.FileEncode",
        "InvalidParameter.InvalidParameter",
        "InvalidParameter.InvalidVocabState",
        "InvalidParameter.KeyWordLibNameExist",
        "InvalidParameter.ModelState",
        "InvalidParameterValue",
        "InvalidParameterValue.ErrorInvalidAppid",
        "InvalidParameterValue.ErrorInvalidClientip",
        "InvalidParameterValue.ErrorInvalidEngservice",
        "InvalidParameterValue.ErrorInvalidProjectid",
        "InvalidParameterValue.ErrorInvalidRequestid",
        "InvalidParameterValue.ErrorInvalidSourcetype",
        "InvalidParameterValue.ErrorInvalidSubservicetype",
        "InvalidParameterValue.ErrorInvalidUrl",
        "InvalidParameterValue.ErrorInvalidUseraudiokey",
        "InvalidParameterValue.ErrorInvalidVoiceFormat",
        "InvalidParameterValue.ErrorInvalidVoicedata",
        "InvalidParameterValue.ErrorVoicedataTooLong",
        "InvalidParameterValue.InvalidParameterLength",
        "InvalidParameterValue.InvalidVocabId",
        "InvalidParameterValue.InvalidVocabState",
        "InvalidParameterValue.InvalidWordWeight",
        "InvalidParameterValue.InvalidWordWeightStr",
        "InvalidParameterValue.ModelId",
        "InvalidParameterValue.NoHumanVoice",
        "InvalidParameterValue.ToState",
        "InvalidRequest",
        "IpInBlacklist",
        "IpNotInWhitelist",
        "LimitExceeded",
        "LimitExceeded.CustomizationFull",
        "LimitExceeded.OnlineFull",
        "LimitExceeded.VocabFull",
        "LimitExceeded.VoicePrintFull",
        "MissingParameter",
        "NoSuchProduct",
        "NoSuchVersion",
        "RequestLimitExceeded",
        "RequestLimitExceeded.GlobalRegionUinLimitExceeded",
        "RequestLimitExceeded.IPLimitExceeded",
        "RequestLimitExceeded.UinLimitExceeded",
        "RequestSizeLimitExceeded",
        "ResourceInUse",
        "ResourceInsufficient",
        "ResourceNotFound",
        "ResourceUnavailable",
        "ResponseSizeLimitExceeded",
        "ServiceUnavailable",
        "UnauthorizedOperation",
        "UnknownParameter",
        "UnsupportedOperation",
        "UnsupportedProtocol",
        "UnsupportedRegion",
    }
)


def test_v2_numeric_catalog_matches_official_doc() -> None:
    """Every 131127 realtime code has a category."""
    assert set(TENCENT_ASR_V2_NUMERIC) == OFFICIAL_V2_NUMERIC
    assert set(TENCENT_ASR_V2_OFFICIAL_ZH) == OFFICIAL_V2_NUMERIC
    for code in OFFICIAL_V2_NUMERIC:
        classified = classify_tencent_asr_error({"code": code, "message": "x"})
        assert classified.category in TENCENT_ASR_ERROR_CATEGORIES
        assert classified.provider_code == str(code)
        assert classified.message == "x"
        assert TENCENT_ASR_V2_OFFICIAL_ZH[code]


def test_35647_string_catalog_matches_official_doc() -> None:
    """Every public + business code on 35647 is mapped, no extras."""
    assert set(TENCENT_ASR_API_STRING) == OFFICIAL_35647_CODES
    for code in OFFICIAL_35647_CODES:
        classified = classify_tencent_asr_error({"Response": {"Error": {"Code": code, "Message": "detail"}}})
        assert classified.category in TENCENT_ASR_ERROR_CATEGORIES
        assert classified.provider_code == code
        assert classified.message == "detail"


def test_signature_and_billing_codes_map_to_actionable_categories() -> None:
    """Console-facing failures keep distinct categories."""
    assert classify_tencent_asr_error({"code": 4002}).category == TENCENT_ASR_CATEGORY_AUTH
    assert (
        classify_tencent_asr_error({"Error": {"Code": "AuthFailure.SignatureFailure"}}).category
        == TENCENT_ASR_CATEGORY_AUTH
    )
    assert classify_tencent_asr_error({"code": 4003}).category == TENCENT_ASR_CATEGORY_SERVICE
    assert (
        classify_tencent_asr_error({"Error": {"Code": "FailedOperation.UserNotRegistered"}}).category
        == TENCENT_ASR_CATEGORY_SERVICE
    )
    assert (
        classify_tencent_asr_error({"Error": {"Code": "FailedOperation.UserHasNoAmount"}}).category
        == TENCENT_ASR_CATEGORY_QUOTA
    )
    assert (
        classify_tencent_asr_error({"Error": {"Code": "FailedOperation.ServiceIsolate"}}).category
        == TENCENT_ASR_CATEGORY_ARREARS
    )
    assert (
        classify_tencent_asr_error({"Error": {"Code": "InvalidParameterValue.ErrorInvalidAppid"}}).category
        == TENCENT_ASR_CATEGORY_APPID
    )
    assert classify_tencent_asr_error({"Error": {"Code": "RequestLimitExceeded"}}).category == TENCENT_ASR_CATEGORY_RPS
    assert (
        classify_tencent_asr_error({"Error": {"Code": "RequestLimitExceeded.IPLimitExceeded"}}).category
        == TENCENT_ASR_CATEGORY_RPS
    )


def test_unknown_string_uses_prefix_fallback() -> None:
    """New AuthFailure.* suffixes still classify as auth."""
    classified = classify_tencent_asr_error({"code": "AuthFailure.BrandNewReason"})
    assert classified.category == TENCENT_ASR_CATEGORY_AUTH
    assert classified.provider_code == "AuthFailure.BrandNewReason"


def test_unknown_5xxx_is_retry() -> None:
    """Future engine codes in the 5xxx band stay retryable."""
    classified = classify_tencent_asr_error({"code": 5099})
    assert classified.category == TENCENT_ASR_CATEGORY_RETRY
    assert classified.provider_code == "5099"


def test_browser_payload_includes_provider_code() -> None:
    """SPA toast uses category; logs can keep the Tencent code."""
    classified = classify_tencent_asr_error({"code": 4004, "message": "pack gone"})
    payload = browser_error_payload(classified)
    assert payload["type"] == "error"
    assert payload["code"] == TENCENT_ASR_CATEGORY_QUOTA
    assert payload["provider_code"] == "4004"
    assert payload["message"] == "pack gone"


def test_empty_payload_is_upstream() -> None:
    """Unparseable failures do not crash the relay."""
    classified = classify_tencent_asr_error({})
    assert classified.category == TENCENT_ASR_CATEGORY_UPSTREAM
    assert classified.provider_code == ""


def test_connect_timeout_is_retryable() -> None:
    """Opening-handshake timeout is a retryable start failure, not a relay crash."""
    classified = tencent_asr_connect_error("timed out during opening handshake")
    assert classified.category == TENCENT_ASR_CATEGORY_RETRY
    assert classified.provider_code == TENCENT_ASR_NO_V2_FRAME
    payload = browser_error_payload(classified)
    assert payload["code"] == TENCENT_ASR_CATEGORY_RETRY
    assert "timed out" in payload["message"]


def test_v2_log_line_uses_official_code_and_text() -> None:
    """Backend logs quote 131127 code + 说明; transport misses map to 5000."""
    classified = classify_tencent_asr_error({"code": 4008, "message": "后台识别服务器音频分片等待超时"})
    line = format_tencent_asr_v2_log(classified, voice_id="vid-1", phase="recognition")
    assert "code=4008" in line
    assert "客户端超过15秒未发送音频数据。" in line
    assert "category=tencent_idle" in line
    assert "voice_id=vid-1" in line
    assert "后台识别服务器音频分片等待超时" in line
    transport = format_tencent_asr_v2_log(
        tencent_asr_connect_error("timed out during opening handshake"),
        phase="opening_handshake",
    )
    assert "code=-" in transport
    assert "equivalent=5000" in transport
    assert "因机器负载过高、网络抖动等导致失败，请重新发起识别。" in transport
