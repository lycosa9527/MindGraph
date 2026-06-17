"""Unit tests for Markets B2C subscription and Alipay notify helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

from models.domain.markets import MarketListing
from services.markets.alipay_common import (
    add_billing_period,
    listing_billing_interval,
    verify_notify_amount,
    verify_notify_app_id,
    yuan_str_to_minor,
)
from services.markets.alipay_settings import AlipayEnvConfig
from services.markets.entitlement_service import entitlement_expires_from_listing


def _cfg() -> AlipayEnvConfig:
    """Cfg."""
    return AlipayEnvConfig(
        app_id="2021000000000000",
        app_private_key="private",
        alipay_public_key="public",
        sandbox=True,
        notify_base_url="https://example.com",
        sign_scene="INDUSTRY|DIGITAL_MEDIA",
        personal_product_code="CYCLE_PAY_AUTH_P",
    )


def test_yuan_str_to_minor() -> None:
    """Test yuan str to minor."""
    assert yuan_str_to_minor("19.90") == 1990
    assert yuan_str_to_minor("0.01") == 1
    assert yuan_str_to_minor("bad") is None


def test_verify_notify_amount() -> None:
    """Test verify notify amount."""
    assert verify_notify_amount("19.90", 1990) is True
    assert verify_notify_amount("19.91", 1990) is False
    assert verify_notify_amount(None, 1990) is False


def test_verify_notify_app_id() -> None:
    """Test verify notify app id."""
    cfg = _cfg()
    assert verify_notify_app_id({"app_id": cfg.app_id}, cfg) is True
    assert verify_notify_app_id({"app_id": "other"}, cfg) is False
    assert verify_notify_app_id({}, cfg) is True


def test_add_billing_period_month() -> None:
    """Test add billing period month."""
    start = datetime(2026, 1, 31, 12, 0, 0)
    end = add_billing_period(start, "month")
    assert end.month == 2
    assert end.day == 28


def test_add_billing_period_year() -> None:
    """Test add billing period year."""
    start = datetime(2026, 2, 28, 8, 0, 0)
    end = add_billing_period(start, "year")
    assert end.year == 2027
    assert end.month == 2
    assert end.day == 28


def test_listing_billing_interval_defaults_month() -> None:
    """Test listing billing interval defaults month."""
    assert listing_billing_interval(None) == "month"
    assert listing_billing_interval({}) == "month"
    assert listing_billing_interval({"interval": "year"}) == "year"


def test_entitlement_expires_from_listing_access_days() -> None:
    """Test entitlement expires from listing access days."""
    paid_at = datetime(2026, 5, 1, tzinfo=UTC).replace(tzinfo=None)
    listing = cast(MarketListing, SimpleNamespace(extra_json={"access_days": 30}))
    expires = entitlement_expires_from_listing(listing, paid_at=paid_at)
    assert expires == paid_at + timedelta(days=30)
