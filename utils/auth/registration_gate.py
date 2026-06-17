"""
Central guard for HTTP registration endpoints controlled by REGISTRATION_ENABLED env.

Covers signup routes and OTP issuance/verification used only for signup
(``purpose=register`` on SMS/email), including peek endpoints ``/sms/verify`` and
``/email/verify``.
"""

from fastapi import HTTPException, status

from models.domain.messages import Language, Messages
from utils.auth import config as auth_configuration


def http_forbid_if_registration_disabled(lang: Language) -> None:
    """
    Raise 403 when REGISTRATION_ENABLED is false.

    Applies to invitation, SMS, overseas email, email OTP, and quick-registration paths.
    """
    if auth_configuration.REGISTRATION_ENABLED:
        return
    detail = Messages.error("registration_disabled", lang=lang)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
