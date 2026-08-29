"""
Query Alipay trade status (``alipay.trade.query``) as page-pay fallback.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any

from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel
from alipay.aop.api.exception.Exception import RequestException, ResponseException
from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest

from services.markets.alipay_client import apply_cert_sns, build_alipay_client
from services.markets.alipay_settings import AlipayEnvConfig

logger = logging.getLogger(__name__)

_PAID_TRADE_STATUSES = frozenset({"TRADE_SUCCESS", "TRADE_FINISHED"})
_QUERY_ERRORS = (
    RequestException,
    ResponseException,
    OSError,
    TimeoutError,
    ValueError,
    TypeError,
    RuntimeError,
)


def _parse_query_payload(text: str) -> dict[str, Any] | None:
    """Extract the query response object, including certificate-mode wrappers."""
    start = text.find("{")
    if start < 0:
        return None
    try:
        parsed = json.loads(text[start:])
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    inner = parsed.get("alipay_trade_query_response")
    if isinstance(inner, dict):
        return inner
    return parsed


def query_trade_by_out_trade_no(cfg: AlipayEnvConfig, out_trade_no: str) -> dict[str, Any] | None:
    """Return parsed ``alipay.trade.query`` body, or None when the gateway call fails."""
    client = build_alipay_client(cfg)
    model = AlipayTradeQueryModel()
    model.out_trade_no = out_trade_no
    request = AlipayTradeQueryRequest(biz_model=model)
    apply_cert_sns(request, cfg)
    try:
        raw = client.execute(request)
    except ResponseException as exc:
        parsed = _parse_query_payload(str(exc))
        if parsed is not None:
            return parsed
        logger.warning("[Markets] Alipay trade.query cert-mode parse failed: %s", exc)
        return None
    except _QUERY_ERRORS as exc:
        logger.warning("[Markets] Alipay trade.query failed: %s", exc)
        return None
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    parsed = _parse_query_payload(str(raw))
    if parsed is None:
        logger.warning("[Markets] Alipay trade.query parse failed")
    return parsed


def query_paid_trade_fields(body: dict[str, Any]) -> tuple[str, str] | None:
    """Return ``(trade_no, total_amount)`` when query says the trade is paid."""
    if str(body.get("code", "")) != "10000":
        return None
    if str(body.get("trade_status", "")) not in _PAID_TRADE_STATUSES:
        return None
    trade_no = str(body.get("trade_no") or "").strip()
    total_amount = str(body.get("total_amount") or "").strip()
    if not trade_no or not total_amount:
        return None
    return trade_no, total_amount
