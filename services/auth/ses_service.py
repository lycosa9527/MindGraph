"""
Tencent Cloud SES (邮件推送) — async HTTP with TC3-HMAC-SHA256.

Sends verification emails via SendEmail (template mode), mirroring the SMS stack.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime
from typing import Optional, Tuple
import hashlib
import hmac
import json
import logging
import os
import random
import string
import time

import httpx

from models.domain.messages import Messages, Language


logger = logging.getLogger(__name__)

_DEFAULT_TEMPLATE_ID = "123456"

TENCENT_SES_SECRET_ID = (
    os.getenv("TENCENT_SES_SECRET_ID", "").strip() or os.getenv("TENCENT_SMS_SECRET_ID", "").strip()
)
TENCENT_SES_SECRET_KEY = (
    os.getenv("TENCENT_SES_SECRET_KEY", "").strip() or os.getenv("TENCENT_SMS_SECRET_KEY", "").strip()
)

TENCENT_SES_REGION = os.getenv("TENCENT_SES_REGION", "ap-hongkong").strip()
TENCENT_SES_HOST = os.getenv("TENCENT_SES_HOST", "ses.ap-hongkong.tencentcloudapi.com").strip()
TENCENT_SES_FROM_EMAIL = os.getenv("TENCENT_SES_FROM_EMAIL", "").strip()
TENCENT_SES_REPLY_TO = os.getenv("TENCENT_SES_REPLY_TO", "").strip()

# Single SES template for all verification-code emails (register, login, reset, change email).
TENCENT_SES_TEMPLATE_ID = os.getenv("TENCENT_SES_TEMPLATE_ID", _DEFAULT_TEMPLATE_ID).strip()

EMAIL_CODE_EXPIRY_MINUTES = int(os.getenv("EMAIL_CODE_EXPIRY_MINUTES", "10"))
EMAIL_RESEND_INTERVAL_SECONDS = int(os.getenv("EMAIL_RESEND_INTERVAL_SECONDS", "60"))
EMAIL_MAX_ATTEMPTS_PER_ADDRESS = int(os.getenv("EMAIL_MAX_ATTEMPTS_PER_ADDRESS", "5"))
EMAIL_MAX_ATTEMPTS_WINDOW_HOURS = int(os.getenv("EMAIL_MAX_ATTEMPTS_WINDOW_HOURS", "1"))
EMAIL_CODE_LENGTH = 6

EMAIL_SUBJECT_REGISTER = os.getenv("EMAIL_SUBJECT_REGISTER", "Your verification code").strip()
EMAIL_SUBJECT_LOGIN = os.getenv("EMAIL_SUBJECT_LOGIN", "Your verification code").strip()
EMAIL_SUBJECT_RESET_PASSWORD = os.getenv("EMAIL_SUBJECT_RESET_PASSWORD", "Your verification code").strip()
EMAIL_SUBJECT_CHANGE_EMAIL = os.getenv("EMAIL_SUBJECT_CHANGE_EMAIL", "Your verification code").strip()

TENCENT_SES_SERVICE = "ses"
TENCENT_SES_VERSION = "2020-10-02"
SES_TIMEOUT_SECONDS = 15


class SESServiceError(Exception):
    """Custom exception for SES service errors."""


class SESService:
    """Tencent Cloud SES SendEmail (native async)."""

    def __init__(self) -> None:
        self._initialized = False
        self._client: Optional[httpx.AsyncClient] = None
        if not all([TENCENT_SES_SECRET_ID, TENCENT_SES_SECRET_KEY, TENCENT_SES_FROM_EMAIL]):
            logger.warning(
                "Tencent SES disabled: set TENCENT_SES_FROM_EMAIL (verified sender in SES console); "
                "SecretId/SecretKey may use TENCENT_SMS_* when TENCENT_SES_SECRET_* are empty."
            )
            return
        self._initialized = True
        logger.info("Tencent SES service initialized (native async mode)")

    @property
    def is_available(self) -> bool:
        return self._initialized

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(SES_TIMEOUT_SECONDS),
                http2=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    def generate_code(self) -> str:
        return "".join(random.choices(string.digits, k=EMAIL_CODE_LENGTH))

    def _sign(self, key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _build_authorization(self, timestamp: int, payload: str, action: str) -> str:
        date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
        http_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        content_type = "application/json"
        canonical_headers = (
            f"content-type:{content_type}\nhost:{TENCENT_SES_HOST}\nx-tc-action:{action.lower()}\n"
        )
        signed_headers = "content-type;host;x-tc-action"
        hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = (
            f"{http_method}\n{canonical_uri}\n{canonical_querystring}\n"
            f"{canonical_headers}\n{signed_headers}\n{hashed_payload}"
        )
        algorithm = "TC3-HMAC-SHA256"
        credential_scope = f"{date}/{TENCENT_SES_SERVICE}/tc3_request"
        hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical}"
        secret_date = self._sign(f"TC3{TENCENT_SES_SECRET_KEY}".encode("utf-8"), date)
        secret_service = self._sign(secret_date, TENCENT_SES_SERVICE)
        secret_signing = self._sign(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        return (
            f"{algorithm} "
            f"Credential={TENCENT_SES_SECRET_ID}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

    def _get_template_id_int(self) -> int:
        try:
            return int(TENCENT_SES_TEMPLATE_ID)
        except ValueError as exc:
            raise ValueError(f"Invalid TENCENT_SES_TEMPLATE_ID: {TENCENT_SES_TEMPLATE_ID!r}") from exc

    def _get_subject(self, purpose: str) -> str:
        subjects = {
            "register": EMAIL_SUBJECT_REGISTER,
            "login": EMAIL_SUBJECT_LOGIN,
            "reset_password": EMAIL_SUBJECT_RESET_PASSWORD,
            "change_email": EMAIL_SUBJECT_CHANGE_EMAIL,
        }
        return subjects.get(purpose, EMAIL_SUBJECT_REGISTER)

    def _translate_error_code(self, code: str, lang: Language) -> str:
        mapping = {
            "FailedOperation.FrequencyLimit": "email_error_frequency_limit",
            "FailedOperation.NotAuthenticatedSender": "email_error_sender_not_authenticated",
            "FailedOperation.InsufficientQuota": "email_error_insufficient_quota",
            "FailedOperation.InsufficientBalance": "email_error_insufficient_balance",
            "FailedOperation.EmailAddrInBlacklist": "email_error_address_blacklisted",
            "FailedOperation.InvalidTemplateID": "email_error_invalid_template",
            "FailedOperation.WrongContentJson": "email_error_template_data",
            "FailedOperation.IncorrectEmail": "email_error_invalid_recipient",
            "FailedOperation.IncorrectSender": "email_error_invalid_sender",
            "FailedOperation.UnsupportMailType": "email_error_unsupported_mail_type",
            "FailedOperation.MissingEmailContent": "email_error_missing_content",
            "InvalidParameterValue.ReceiverEmailInvalid": "email_error_invalid_recipient",
            "InvalidParameterValue.EmailAddressIsNULL": "email_error_invalid_recipient",
            "InvalidParameterValue.InvalidEmailIdentity": "email_error_invalid_domain",
            "InvalidParameterValue.EmailContentIsWrong": "email_error_template_data",
            "AuthFailure.UnauthorizedOperation": "email_error_unauthorized",
            "RequestLimitExceeded": "email_error_rate_limit",
        }
        key = mapping.get(code, "email_error_generic")
        return Messages.error(key, lang)

    async def send_verification_code(
        self,
        email: str,
        purpose: str,
        code: Optional[str] = None,
        lang: Language = "en",
    ) -> Tuple[bool, str, Optional[str]]:
        if not self.is_available:
            return False, "SES service not available", None

        if not code:
            code = self.generate_code()

        try:
            template_id = self._get_template_id_int()
        except ValueError as exc:
            logger.error("SES template id: %s", exc)
            return False, Messages.error("email_error_invalid_template", lang), None

        subject = self._get_subject(purpose)
        template_data = json.dumps({"CODE": code})

        body: dict = {
            "FromEmailAddress": TENCENT_SES_FROM_EMAIL,
            "Destination": [email],
            "Subject": subject,
            "Template": {
                "TemplateID": template_id,
                "TemplateData": template_data,
            },
            "TriggerType": 1,
            "Unsubscribe": "0",
        }
        if TENCENT_SES_REPLY_TO:
            body["ReplyToAddresses"] = TENCENT_SES_REPLY_TO

        payload = json.dumps(body)
        timestamp = int(time.time())
        action = "SendEmail"
        endpoint = f"https://{TENCENT_SES_HOST}"

        headers = {
            "Authorization": self._build_authorization(timestamp, payload, action),
            "Content-Type": "application/json",
            "Host": TENCENT_SES_HOST,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": TENCENT_SES_VERSION,
            "X-TC-Region": TENCENT_SES_REGION,
        }

        try:
            client = await self._get_client()
            response = await client.post(endpoint, content=payload, headers=headers)
        except httpx.TimeoutException:
            logger.error("SES request timeout")
            return False, Messages.error("email_error_timeout", lang), None
        except httpx.HTTPError as exc:
            logger.error("SES HTTP error: %s", exc)
            return False, Messages.error("email_error_http", lang), None

        if response.status_code != 200:
            logger.error("SES API non-200: %s %s", response.status_code, response.text[:200])
            return False, Messages.error("email_error_http", lang), None

        try:
            result = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            logger.error("SES JSON parse error: %s", exc)
            return False, Messages.error("email_error_generic", lang), None

        if "Response" not in result:
            logger.error("Invalid SES response: %s", result)
            return False, Messages.error("email_error_generic", lang), None

        resp_data = result["Response"]
        if "Error" in resp_data:
            err = resp_data["Error"]
            error_code = err.get("Code", "Unknown")
            logger.error("SES API error: %s - %s", error_code, err.get("Message", ""))
            return False, self._translate_error_code(error_code, lang), None

        if resp_data.get("MessageId"):
            logger.info("SES sent MessageId=%s purpose=%s", resp_data.get("MessageId"), purpose)
            return True, Messages.success("verification_email_sent", lang), code

        logger.error("Unexpected SES response: %s", resp_data)
        return False, Messages.error("email_error_generic", lang), None
