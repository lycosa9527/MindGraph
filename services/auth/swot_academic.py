"""
JetBrains Swot–based academic email check (rse-pyswot) plus Kikobeats free domains.

Uses bundled Swot data (pyswot) and committed Kikobeats domains.json for local checks.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import HTTPException, status

from models.domain.messages import Language, Messages
from utils.auth.overseas_registration_messages import overseas_registration_message_key
from utils.auth.swot_config import is_swot_academic_required_for_purpose
from utils.email_mainland_china import is_mainland_china_email_domain


logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_kikobeats_free_domains() -> frozenset[str]:
    path = _repo_root() / "data" / "kikobeats_free_email_domains.json"
    if not path.is_file():
        msg = f"Missing required Kikobeats list: {path}"
        raise RuntimeError(msg)
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        msg = f"Invalid Kikobeats JSON (expected array): {path}"
        raise RuntimeError(msg)
    return frozenset(str(x).strip().lower() for x in data if str(x).strip())


_KIKOBEATS_FREE: frozenset[str] = _load_kikobeats_free_domains()


def _email_host(email: str) -> str:
    return email.strip().split("@")[-1].strip().lower()


def _host_in_kikobeats_free(host: str) -> bool:
    host = host.strip().lower()
    parts = host.split(".")
    for i in range(len(parts)):
        candidate = ".".join(parts[i:])
        if candidate in _KIKOBEATS_FREE:
            return True
    return False


def passes_combined_academic_policy(email: str) -> bool:
    """
    True iff registrable host is not a Kikobeats free domain and pyswot.is_academic is True.

    Order: Kikobeats (frozenset), mainland China domain policy (no pyswot country API), then pyswot.
    """
    if _host_in_kikobeats_free(_email_host(email)):
        return False
    if is_mainland_china_email_domain(_email_host(email)):
        return False
    try:
        from pyswot import is_academic
    except ImportError:
        logger.error("pyswot is not installed; cannot run academic email check")
        return False

    try:
        return bool(is_academic(email))
    except Exception as exc:
        logger.error("pyswot is_academic failed for email: %s", exc)
        return False


def is_academic_email_required_for_purpose(purpose: str) -> bool:
    """True when SWOT academic enforcement is enabled for the given purpose."""
    return is_swot_academic_required_for_purpose(purpose)


def is_academic_email(email: str) -> bool:
    """
    Same predicate as enforcement: Kikobeats block, mainland China domain block, then Swot.

    On unexpected errors from pyswot, logs and returns False (conservative for allow checks).
    """
    return passes_combined_academic_policy(email)


def require_academic_email_if_configured(email: str, purpose: str, lang: Language) -> None:
    """
    If SWOT enforcement is enabled and `purpose` is in the configured set,
    raise HTTP 400 when the email does not pass the combined academic policy.
    """
    if not is_swot_academic_required_for_purpose(purpose):
        return

    if _host_in_kikobeats_free(_email_host(email)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("email_not_academic_domain", lang),
        ) from None

    if is_mainland_china_email_domain(_email_host(email)):
        msg_key = overseas_registration_message_key("registration_email_mainland_china_domain")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error(msg_key, lang),
        ) from None

    try:
        from pyswot import is_academic
    except ImportError:
        logger.error("SWOT_ACADEMIC_EMAIL_REQUIRED is true but pyswot is not installed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Messages.error("email_swot_unavailable", lang),
        ) from None

    try:
        ok = bool(is_academic(email))
    except Exception as exc:
        logger.error("pyswot is_academic failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Messages.error("email_swot_unavailable", lang),
        ) from exc

    if ok:
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=Messages.error("email_not_academic_domain", lang),
    )
