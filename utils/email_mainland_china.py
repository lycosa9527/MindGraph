"""
Detect email domains associated with mainland China for overseas registration and email login policy.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from fastapi import HTTPException, status

from models.domain.messages import Language, Messages


# Consumer / campus mail hosts commonly used in mainland China (not exhaustive).
_MAINLAND_BLOCKLIST_ROOTS: frozenset[str] = frozenset(
    {
        "qq.com",
        "foxmail.com",
        "163.com",
        "126.com",
        "163.net",
        "sina.com",
        "sina.cn",
        "sohu.com",
        "yeah.net",
        "aliyun.com",
        "139.com",
        "189.cn",
        "21cn.com",
        "tom.com",
        "wo.cn",
        "263.net",
        "188.com",
        "wo.com.cn",
    }
)


def is_mainland_china_email_domain(host: str) -> bool:
    """
    True if the email domain is treated as mainland China for overseas registration.

    Any host ending in .cn is mainland. Additional .com/.net hosts that are
    overwhelmingly PRC consumer mail are blocked.
    """
    host = host.strip().lower()
    if not host:
        return False
    if host.endswith(".cn"):
        return True
    for root in _MAINLAND_BLOCKLIST_ROOTS:
        if host == root or host.endswith("." + root):
            return True
    return False


def _raise_if_mainland_china_email(email: str, lang: Language, message_key: str) -> None:
    parts = email.strip().rsplit("@", 1)
    if len(parts) != 2:
        return
    host = parts[1].strip()
    if is_mainland_china_email_domain(host):
        detail = Messages.error(message_key, lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def raise_if_mainland_china_email_for_overseas_registration(email: str, lang: Language) -> None:
    """Reject overseas education-email registration when the domain is mainland China."""
    _raise_if_mainland_china_email(email, lang, "registration_email_mainland_china_domain")


def raise_if_mainland_china_email_for_email_login(email: str, lang: Language) -> None:
    """Reject email-based login when the domain is mainland China (password or OTP)."""
    _raise_if_mainland_china_email(email, lang, "email_login_mainland_china_domain")
