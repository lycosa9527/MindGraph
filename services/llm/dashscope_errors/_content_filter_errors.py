"""
Content Filter Error Parser
============================

Handles content filtering and policy violation errors.
"""
from typing import Optional, Tuple

from services.infrastructure.http.error_handler import (
    LLMQuotaExhaustedError,
    LLMContentFilterError
)


def parse_content_filter_errors(
    error_message: str,
    error_msg_lower: str,
    error_code: str,
    has_chinese: bool
) -> Optional[Tuple[Exception, str]]:
    """Parse content filter errors."""
    # 400 Arrearage (Account in arrears)
    if (error_code == 'Arrearage' or
            ('arrearage' in error_msg_lower and
             'access denied' in error_msg_lower)):
        if has_chinese:
            user_msg = "账户欠费，访问被拒绝。请前往费用与成本查看并充值"
        else:
            user_msg = (
                "Account in arrears, access denied. Please check billing "
                "and recharge."
            )
        return LLMQuotaExhaustedError(
            f"Account in arrears: {error_message}",
            provider='dashscope',
            error_code=error_code or 'Arrearage'
        ), user_msg

    # 400 DataInspectionFailed (Content filter)
    if (error_code in ['DataInspectionFailed', 'data_inspection_failed',
                       'DataInspection', 'InvalidParameter.DataInspection'] or
            'inappropriate content' in error_msg_lower or
            'data inspection' in error_msg_lower):
        if 'input' in error_msg_lower and 'output' in error_msg_lower:
            if has_chinese:
                user_msg = "输入或输出可能包含不当内容，请修改输入内容"
            else:
                user_msg = (
                    "Input or output may contain inappropriate content. "
                    "Please modify input."
                )
        elif 'input' in error_msg_lower:
            if has_chinese:
                user_msg = "输入可能包含不当内容，请修改输入内容"
            else:
                user_msg = (
                    "Input may contain inappropriate content. "
                    "Please modify input."
                )
        elif 'output' in error_msg_lower:
            if has_chinese:
                user_msg = "输出可能包含不当内容，请修改输入后重试"
            else:
                user_msg = (
                    "Output may contain inappropriate content. "
                    "Please modify input and retry."
                )
        else:
            if has_chinese:
                user_msg = "内容可能包含不当信息，请修改输入内容"
            else:
                user_msg = (
                    "Content may contain inappropriate information. "
                    "Please modify input."
                )
        return LLMContentFilterError(f"Content filter: {error_message}"), user_msg

    # 400 IP Infringement
    if (error_code == 'IPInfringementSuspect' or
            'ip infringement' in error_msg_lower or
            'intellectual property' in error_msg_lower):
        if has_chinese:
            user_msg = "输入内容涉嫌知识产权侵权，请检查输入内容"
        else:
            user_msg = (
                "Input may involve intellectual property infringement. "
                "Please check input."
            )
        return LLMContentFilterError(f"IP infringement: {error_message}"), user_msg

    # 400 FAQ Rule Blocked
    if (error_code == 'FaqRuleBlocked' or
            'faq rule' in error_msg_lower or
            'blocked by faq' in error_msg_lower):
        user_msg = "输入或输出数据被FAQ规则拦截" if has_chinese else "Input or output blocked by FAQ rule."
        return LLMContentFilterError(f"FAQ rule blocked: {error_message}"), user_msg

    # 400 Custom Role Blocked
    if (error_code == 'CustomRoleBlocked' or
            'custom rule' in error_msg_lower or
            'custom role blocked' in error_msg_lower):
        user_msg = "输入或输出数据未通过自定义策略" if has_chinese else "Input or output failed custom policy check."
        return LLMContentFilterError(f"Custom rule blocked: {error_message}"), user_msg

    return None
