"""Unit tests for Alipay PC page-pay contract (open-v3 电脑网站支付)."""

from __future__ import annotations

from typing import Any

from services.markets.alipay_common import (
    PAGE_PAY_PRODUCT_CODE,
    markets_return_url,
    page_pay_subject,
)
from services.markets.alipay_page_pay import build_page_pay_form_html
from services.markets.alipay_settings import (
    ALIPAY_GATEWAY_PRODUCTION,
    ALIPAY_GATEWAY_SANDBOX,
    AlipayEnvConfig,
)
from services.markets.alipay_trade_query import _parse_query_payload, query_paid_trade_fields


def _cfg(*, sandbox: bool = False) -> AlipayEnvConfig:
    """Minimal Alipay env for unit tests."""
    return AlipayEnvConfig(
        app_id="2021000000000000",
        app_private_key="private",
        alipay_public_key="public",
        sandbox=sandbox,
        notify_base_url="https://example.com",
        sign_scene="INDUSTRY|DIGITAL_MEDIA",
        personal_product_code="CYCLE_PAY_AUTH_P",
    )


def test_gateway_urls_match_current_alipay_hosts() -> None:
    """Test gateway urls match current alipay hosts."""
    assert _cfg(sandbox=False).server_url == ALIPAY_GATEWAY_PRODUCTION
    assert _cfg(sandbox=True).server_url == ALIPAY_GATEWAY_SANDBOX
    assert ALIPAY_GATEWAY_SANDBOX == "https://openapi-sandbox.dl.alipaydev.com/gateway.do"


def test_page_pay_subject_strips_forbidden_chars() -> None:
    """Test page pay subject strips forbidden chars."""
    assert page_pay_subject("  A/B = C & D  ") == "A B C D"
    assert len(page_pay_subject("x" * 300)) == 256


def test_markets_return_url_includes_order_id() -> None:
    """Test markets return url includes order id."""
    assert markets_return_url("https://mg.example.com/") == ("https://mg.example.com/template?alipay=return")
    assert markets_return_url("https://mg.example.com", order_id=42) == (
        "https://mg.example.com/template?alipay=return&order_id=42"
    )
    assert markets_return_url("") is None


def test_build_page_pay_form_sets_v3_required_fields(monkeypatch: Any) -> None:
    """Test build page pay form sets v3 required fields."""
    captured: dict[str, Any] = {}

    class FakeClient:
        """Capture page_execute arguments."""

        def page_execute(self, request: Any, http_method: str = "POST") -> str:
            """Record the request and return a stub form."""
            captured["http_method"] = http_method
            captured["notify_url"] = request.notify_url
            captured["return_url"] = request.return_url
            captured["model"] = request.biz_model
            return "<form id='alipaysubmit'></form>"

    monkeypatch.setattr(
        "services.markets.alipay_page_pay.build_alipay_client",
        lambda cfg: FakeClient(),
    )
    html = build_page_pay_form_html(
        cfg=_cfg(),
        out_trade_no="MG1abc",
        total_amount_yuan="19.90",
        subject="模板/测试&标题",
        notify_url="https://example.com/api/markets/payments/alipay/notify",
        return_url="https://example.com/template?alipay=return&order_id=9",
    )
    assert "<form" in html
    assert captured["http_method"] == "POST"
    model = captured["model"]
    assert model.out_trade_no == "MG1abc"
    assert model.total_amount == "19.90"
    assert model.product_code == PAGE_PAY_PRODUCT_CODE
    assert model.product_code == "FAST_INSTANT_TRADE_PAY"
    assert model.subject == "模板 测试 标题"
    assert model.integration_type == "PCWEB"
    assert captured["notify_url"].endswith("/api/markets/payments/alipay/notify")
    assert "order_id=9" in captured["return_url"]


def test_parse_cert_mode_query_wrapper() -> None:
    """Test parse cert mode query wrapper."""
    wrapped = (
        'prefix {"alipay_trade_query_response":{"code":"40004",'
        '"sub_code":"ACQ.TRADE_NOT_EXIST"},"alipay_cert_sn":"abc","sign":"x"}'
    )
    body = _parse_query_payload(wrapped)
    assert body is not None
    assert body["sub_code"] == "ACQ.TRADE_NOT_EXIST"


def test_query_paid_trade_fields() -> None:
    """Test query paid trade fields."""
    paid = query_paid_trade_fields(
        {
            "code": "10000",
            "trade_status": "TRADE_SUCCESS",
            "trade_no": "2026082922001",
            "total_amount": "19.90",
        }
    )
    assert paid == ("2026082922001", "19.90")
    assert query_paid_trade_fields({"code": "10000", "trade_status": "WAIT_BUYER_PAY"}) is None
    assert query_paid_trade_fields({"code": "40004"}) is None
