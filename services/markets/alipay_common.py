"""Shared helpers for Markets Alipay integration."""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional

from services.markets.alipay_settings import AlipayEnvConfig


def minor_to_yuan_str(price_minor: int) -> str:
    return f"{price_minor / 100.0:.2f}"


def yuan_str_to_minor(total_amount: str) -> Optional[int]:
    try:
        value = Decimal(str(total_amount).strip())
    except (InvalidOperation, ValueError):
        return None
    return int((value * 100).quantize(Decimal("1")))


def get_notify_str(data: Mapping[str, Any], key: str) -> str | None:
    raw = data.get(key)
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)) and raw:
        return str(raw[0])
    return str(raw)


def trade_notify_url(cfg: AlipayEnvConfig) -> str:
    return f"{cfg.notify_base_url.rstrip('/')}/api/markets/payments/alipay/notify"


def verify_notify_app_id(params: Mapping[str, Any], cfg: AlipayEnvConfig) -> bool:
    app_id = get_notify_str(params, "app_id")
    return app_id is None or app_id == cfg.app_id


def verify_notify_amount(total_amount: str | None, expected_minor: int) -> bool:
    if total_amount is None:
        return False
    parsed = yuan_str_to_minor(total_amount)
    return parsed is not None and parsed == expected_minor


def add_billing_period(start: datetime, interval: str) -> datetime:
    """Advance ``start`` by one billing interval (month or year)."""
    if interval == "year":
        target_year = start.year + 1
        last_day = monthrange(target_year, start.month)[1]
        day = min(start.day, last_day)
        return start.replace(year=target_year, month=start.month, day=day)

    target_month = start.month + 1
    target_year = start.year
    if target_month > 12:
        target_month = 1
        target_year += 1
    last_day = monthrange(target_year, target_month)[1]
    day = min(start.day, last_day)
    return start.replace(year=target_year, month=target_month, day=day)


def listing_billing_interval(listing_extra: Optional[dict[str, Any]]) -> str:
    if not listing_extra:
        return "month"
    interval = listing_extra.get("interval")
    if isinstance(interval, str) and interval in ("month", "year"):
        return interval
    return "month"


def listing_execute_time(listing_extra: Optional[dict[str, Any]]) -> str:
    if not listing_extra:
        return "08:00"
    execute_time = listing_extra.get("execute_time")
    if isinstance(execute_time, str) and execute_time:
        return execute_time
    return "08:00"


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
