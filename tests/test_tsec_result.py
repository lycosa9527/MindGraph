"""DescribeCaptchaResult parameter parse + [TsecAudit] logging."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from services.auth.tsec.client import TsecCaptchaClientError, build_describe_captcha_body
from services.auth.tsec.result import (
    TsecVerifyTrace,
    audit_kind,
    log_tsec_audit,
    parse_describe_response,
    parse_disaster_ticket,
    ticket_prefix,
)
from services.auth.tsec.verify import verify_tsec_ticket


def test_build_describe_body_sets_need_get_captcha_time(monkeypatch) -> None:
    """NeedGetCaptchaTime=1 is required to receive GetCaptchaTime."""
    monkeypatch.setenv("TENCENT_CAPTCHA_APP_ID", "196175536")
    monkeypatch.setenv("TENCENT_CAPTCHA_APP_SECRET_KEY", "test-secret")
    monkeypatch.delenv("TENCENT_CAPTCHA_BUSINESS_ID", raising=False)
    monkeypatch.delenv("TENCENT_CAPTCHA_SCENE_ID", raising=False)
    body = build_describe_captcha_body("tr03ticket", "@Vki", "1.2.3.4")
    assert body["CaptchaType"] == 9
    assert body["NeedGetCaptchaTime"] == 1
    assert body["Ticket"] == "tr03ticket"
    assert body["Randstr"] == "@Vki"
    assert body["UserIp"] == "1.2.3.4"
    assert body["CaptchaAppId"] == 196175536
    assert "BusinessId" not in body
    assert "SceneId" not in body
    assert "MacAddress" not in body
    assert "Imei" not in body


def test_build_describe_body_includes_reserved_ids(monkeypatch) -> None:
    """Reserved BusinessId/SceneId are sent only when configured."""
    monkeypatch.setenv("TENCENT_CAPTCHA_APP_ID", "196175536")
    monkeypatch.setenv("TENCENT_CAPTCHA_APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("TENCENT_CAPTCHA_BUSINESS_ID", "1")
    monkeypatch.setenv("TENCENT_CAPTCHA_SCENE_ID", "3")
    body = build_describe_captcha_body("tr03ticket", "@Vki", "1.2.3.4")
    assert body["BusinessId"] == 1
    assert body["SceneId"] == 3


def test_parse_describe_response_reads_all_output_fields() -> None:
    """Every documented DescribeCaptchaResult output field is captured."""
    parsed = parse_describe_response(
        {
            "CaptchaCode": 1,
            "CaptchaMsg": "OK",
            "EvilLevel": 0,
            "GetCaptchaTime": 1729583235,
            "EvilBitmap": 0,
            "SubmitCaptchaTime": 1729583239,
            "DeviceRiskCategory": "301",
            "Score": 60,
            "RequestId": "req-1",
        }
    )
    assert parsed.captcha_code == 1
    assert parsed.captcha_msg == "OK"
    assert parsed.evil_level == 0
    assert parsed.get_captcha_time == 1729583235
    assert parsed.evil_bitmap == 0
    assert parsed.submit_captcha_time == 1729583239
    assert parsed.device_risk_category == "301"
    assert parsed.score == 60
    assert parsed.request_id == "req-1"
    assert parsed.code_parse_error is False


def test_ticket_prefix_truncates() -> None:
    """Audit logs must not print the full ticket."""
    assert ticket_prefix("short") == "short"
    assert ticket_prefix("tr03XaCUZPAlPdIMqv17yvcfdXCzkqvLE09") == "tr03XaCUZPAlPdIMqv17..."


def test_log_tsec_audit_includes_api_and_trace_fields(caplog: pytest.LogCaptureFixture) -> None:
    """Pass and reject lines carry the parsed API snapshot plus frontend trace."""
    parsed = parse_describe_response(
        {
            "CaptchaCode": 1,
            "CaptchaMsg": "OK",
            "EvilLevel": 0,
            "GetCaptchaTime": 100,
            "SubmitCaptchaTime": 104,
            "Score": 80,
            "RequestId": "rid",
        }
    )
    with caplog.at_level("INFO"):
        log_tsec_audit(
            "pass",
            "ok",
            "8.8.8.8",
            "tr03longticketvaluehere",
            parsed=parsed,
            trace=TsecVerifyTrace(sid="sid-1", verify_duration=120, action_duration=90),
        )
    text = caplog.text
    assert "[TsecAudit] outcome=pass kind=pass reason=ok ip=8.8.8.8" in text
    assert "captcha_code=1" in text
    assert "get_time=100" in text
    assert "submit_time=104" in text
    assert "score=80" in text
    assert "sid=sid-1" in text
    assert "verify_ms=120" in text
    assert "action_ms=90" in text
    assert "tr03longticketvaluehere" not in text


@pytest.mark.asyncio
async def test_verify_logs_full_result_on_pass(caplog: pytest.LogCaptureFixture) -> None:
    """A successful ticket check writes one [TsecAudit] pass line."""
    with patch(
        "services.auth.tsec.verify.describe_captcha_result",
        return_value={
            "CaptchaCode": 1,
            "CaptchaMsg": "OK",
            "EvilLevel": 0,
            "GetCaptchaTime": 11,
            "SubmitCaptchaTime": 15,
            "EvilBitmap": 0,
            "DeviceRiskCategory": "301",
            "Score": 55,
            "RequestId": "abc",
        },
    ):
        with caplog.at_level("INFO"):
            ok, reason = await verify_tsec_ticket("tr03validticket", "@Vki", "1.1.1.1")
    assert ok is True
    assert reason is None
    assert "[TsecAudit] outcome=pass kind=pass reason=ok" in caplog.text
    assert "device_risk=301" in caplog.text
    assert "request_id=abc" in caplog.text


@pytest.mark.asyncio
async def test_verify_logs_client_error(caplog: pytest.LogCaptureFixture) -> None:
    """Cloud API failures still emit [TsecAudit] with the client error token."""
    with patch(
        "services.auth.tsec.verify.describe_captcha_result",
        side_effect=TsecCaptchaClientError("UnauthorizedOperation.Unauthorized"),
    ):
        with caplog.at_level("WARNING"):
            ok, reason = await verify_tsec_ticket("tr03validticket", "@Vki", "9.9.9.9")
    assert ok is False
    assert reason == "cloud_api_unauthorized"
    assert "client_error=UnauthorizedOperation.Unauthorized" in caplog.text
    assert "kind=provider" in caplog.text
    assert "ip=9.9.9.9" in caplog.text


@pytest.mark.parametrize(
    ("outcome", "reason", "expected"),
    [
        ("pass", "ok", "pass"),
        ("reject", "evil_level", "abuse"),
        ("reject", "ticket_diff", "abuse"),
        ("reject", "randstr_mismatch", "abuse"),
        ("reject", "disaster_ticket", "client"),
        ("reject", "appid_secretkey_mismatch", "config"),
        ("reject", "ticket_expired", "replay"),
        ("reject", "cloud_api_unauthorized", "provider"),
        ("reject", "provider_error", "provider"),
    ],
)
def test_audit_kind_classifies_pdf_cases(outcome: str, reason: str, expected: str) -> None:
    """PDF CaptchaCode guidance maps onto grep-friendly kind= values."""
    assert audit_kind(outcome, reason) == expected


def test_parse_disaster_ticket_matches_pdf_format() -> None:
    """trerror_{errorCode}_{CaptchaAppId}_{unix} is the official disaster ticket."""
    error_code, app_id = parse_disaster_ticket("trerror_1006_196175536_1710000000")
    assert error_code == "1006"
    assert app_id == "196175536"
    assert parse_disaster_ticket("tr03real") == (None, None)
