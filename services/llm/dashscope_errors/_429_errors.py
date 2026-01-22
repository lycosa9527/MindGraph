"""
429 Rate Limit Error Parser
============================

Handles rate limiting and quota exhaustion errors.
"""
from typing import Optional, Tuple

from services.infrastructure.http.error_handler import (
    LLMRateLimitError,
    LLMQuotaExhaustedError
)


def parse_429_errors(
    error_message: str,
    error_msg_lower: str,
    error_code: str,
    has_chinese: bool
) -> Optional[Tuple[Exception, str]]:
    """Parse 429 Rate Limit errors."""
    # General throttling
    if (error_code == 'Throttling' or
            'throttling' in error_msg_lower or
            'rate limit' in error_msg_lower):
        if has_chinese:
            user_msg = "请求过于频繁，请降低调用频率或稍后重试"
        else:
            user_msg = (
                "Rate limit exceeded. Please reduce call frequency or "
                "try again later."
            )
        return LLMRateLimitError(f"Rate limit: {error_message}"), user_msg

    # Rate quota exceeded
    if (error_code == 'Throttling.RateQuota' or
            error_code == 'LimitRequests' or
            'request limit exceeded' in error_msg_lower):
        if has_chinese:
            user_msg = "请求频率（RPS/RPM）触发限流，请控制调用频率"
        else:
            user_msg = (
                "Request rate (RPS/RPM) limit exceeded. "
                "Please control call frequency."
            )
        return LLMRateLimitError(f"Rate quota exceeded: {error_message}"), user_msg

    # Burst rate limit
    if (error_code == 'Throttling.BurstRate' or
            'burst rate' in error_msg_lower or
            'rate increased too quickly' in error_msg_lower):
        if has_chinese:
            user_msg = (
                "请求频率增长过快，请优化客户端调用逻辑，采用平滑请求策略"
            )
        else:
            user_msg = (
                "Request rate increased too quickly. Optimize client logic "
                "with smooth request strategy."
            )
        return LLMRateLimitError(f"Burst rate limit: {error_message}"), user_msg

    # Allocation quota (TPS/TPM)
    if (error_code == 'Throttling.AllocationQuota' or
            'allocation quota' in error_msg_lower or
            ('quota exceeded' in error_msg_lower and
             'token' in error_msg_lower)):
        if has_chinese:
            user_msg = "Token消耗速度（TPS/TPM）触发限流，请调整调用策略"
        else:
            user_msg = (
                "Token consumption rate (TPS/TPM) limit exceeded. "
                "Please adjust call strategy."
            )
        return LLMQuotaExhaustedError(
            f"Allocation quota exceeded: {error_message}",
            provider='dashscope',
            error_code=error_code or 'Throttling.AllocationQuota'
        ), user_msg

    # Commodity not purchased
    if (error_code == 'CommodityNotPurchased' or
            'commodity has not purchased' in error_msg_lower):
        if has_chinese:
            user_msg = "业务空间未订购，请先订购业务空间服务"
        else:
            user_msg = (
                "Commodity not purchased. Please purchase workspace service "
                "first."
            )
        return LLMQuotaExhaustedError(
            f"Commodity not purchased: {error_message}",
            provider='dashscope',
            error_code=error_code or 'CommodityNotPurchased'
        ), user_msg

    # Prepaid bill overdue
    if (error_code == 'PrepaidBillOverdue' or
            'prepaid bill is overdue' in error_msg_lower):
        if has_chinese:
            user_msg = "业务空间预付费账单到期，请续费"
        else:
            user_msg = "Prepaid bill overdue. Please renew."
        return LLMQuotaExhaustedError(
            f"Prepaid bill overdue: {error_message}",
            provider='dashscope',
            error_code=error_code or 'PrepaidBillOverdue'
        ), user_msg

    # Postpaid bill overdue
    if (error_code == 'PostpaidBillOverdue' or
            'postpaid bill is overdue' in error_msg_lower):
        if has_chinese:
            user_msg = "模型推理商品已失效，请检查账单状态"
        else:
            user_msg = (
                "Postpaid bill overdue. Model inference service expired. "
                "Please check billing status."
            )
        return LLMQuotaExhaustedError(
            f"Postpaid bill overdue: {error_message}",
            provider='dashscope',
            error_code=error_code or 'PostpaidBillOverdue'
        ), user_msg

    # Too many fine-tune jobs
    if 'too many fine-tune job' in error_msg_lower:
        if has_chinese:
            user_msg = "运行中的微调任务过多，请删除不再使用的模型或申请提额"
        else:
            user_msg = (
                "Too many fine-tune jobs running. Please delete unused "
                "models or request quota increase."
            )
        return LLMRateLimitError(f"Too many fine-tune jobs: {error_message}"), user_msg

    # Batch throttling
    if 'batch requests are being throttled' in error_msg_lower:
        if has_chinese:
            user_msg = "Batch请求过多触发限流，请稍后重试"
        else:
            user_msg = (
                "Batch requests throttled due to system capacity limits. "
                "Please try again later."
            )
        return LLMRateLimitError(f"Batch throttling: {error_message}"), user_msg

    if has_chinese:
        user_msg = "请求过于频繁，请稍后重试"
    else:
        user_msg = "Rate limit exceeded. Please try again later."
    return LLMRateLimitError(f"Rate limit: {error_message}"), user_msg
