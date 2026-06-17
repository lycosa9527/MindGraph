"""
Cancel Alipay periodic agreement (subscription unsign).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from alipay.aop.api.domain.AlipayUserAgreementUnsignModel import AlipayUserAgreementUnsignModel
from alipay.aop.api.request.AlipayUserAgreementUnsignRequest import AlipayUserAgreementUnsignRequest

from services.markets.alipay_client import build_alipay_client
from services.markets.alipay_settings import AlipayEnvConfig

logger = logging.getLogger(__name__)


def unsign_agreement(*, cfg: AlipayEnvConfig, agreement_no: str) -> None:
    """Call ``alipay.user.agreement.unsign``; raises on gateway error response."""
    client = build_alipay_client(cfg)
    model = AlipayUserAgreementUnsignModel()
    model.agreement_no = agreement_no
    request = AlipayUserAgreementUnsignRequest(biz_model=model)
    response = client.execute(request)
    if response is None:
        raise RuntimeError("Alipay unsign returned empty response")
    body = str(response)
    if "error_response" in body or "code" in body and '"10000"' not in body:
        logger.warning("[Markets] Alipay unsign response: %s", body[:500])
        if "10000" not in body:
            raise RuntimeError(f"Alipay unsign failed: {body[:300]}")
