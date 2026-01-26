"""
SMS Service Module

Tencent Cloud SMS Service implementation.
Provides native async HTTP calls with TC3-HMAC-SHA256 signature,
bypassing the synchronous Tencent SDK entirely.

Features:
- Native async HTTP calls via httpx
- Error handling and translation
- Phone number formatting
- Verification code generation

@author lycosa9527
@made_by MindSpring Team

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

# ============================================================================
# Configuration
# ============================================================================

# Tencent Cloud credentials
TENCENT_SECRET_ID = os.getenv("TENCENT_SMS_SECRET_ID", "").strip()
TENCENT_SECRET_KEY = os.getenv("TENCENT_SMS_SECRET_KEY", "").strip()

# SMS settings
SMS_SDK_APP_ID = os.getenv("TENCENT_SMS_SDK_APP_ID", "").strip()
SMS_SIGN_NAME = os.getenv("TENCENT_SMS_SIGN_NAME", "").strip()
SMS_REGION = os.getenv("TENCENT_SMS_REGION", "ap-guangzhou").strip()

# Template IDs for different purposes
SMS_TEMPLATE_REGISTER = os.getenv("TENCENT_SMS_TEMPLATE_REGISTER", "").strip()
SMS_TEMPLATE_LOGIN = os.getenv("TENCENT_SMS_TEMPLATE_LOGIN", "").strip()
SMS_TEMPLATE_RESET_PASSWORD = os.getenv("TENCENT_SMS_TEMPLATE_RESET_PASSWORD", "").strip()
SMS_TEMPLATE_CHANGE_PHONE = os.getenv("TENCENT_SMS_TEMPLATE_CHANGE_PHONE", "").strip()
SMS_TEMPLATE_ALERT = os.getenv("TENCENT_SMS_TEMPLATE_ALERT", "").strip()

# Rate limiting configuration (database-level)
SMS_CODE_EXPIRY_MINUTES = int(os.getenv("SMS_CODE_EXPIRY_MINUTES", "5"))
SMS_RESEND_INTERVAL_SECONDS = int(os.getenv("SMS_RESEND_INTERVAL_SECONDS", "60"))
SMS_MAX_ATTEMPTS_PER_PHONE = int(os.getenv("SMS_MAX_ATTEMPTS_PER_PHONE", "5"))
SMS_MAX_ATTEMPTS_WINDOW_HOURS = int(os.getenv("SMS_MAX_ATTEMPTS_WINDOW_HOURS", "1"))

# Verification code length
SMS_CODE_LENGTH = 6

# Tencent API settings
TENCENT_SMS_HOST = "sms.tencentcloudapi.com"
TENCENT_SMS_ENDPOINT = f"https://{TENCENT_SMS_HOST}"
TENCENT_SMS_SERVICE = "sms"
TENCENT_SMS_VERSION = "2021-01-11"

# HTTP client timeout
SMS_TIMEOUT_SECONDS = 10


class SMSServiceError(Exception):
    """Custom exception for SMS service errors"""


class SMSService:
    """
    Tencent Cloud SMS Service (Native Async)

    Uses direct HTTP calls with TC3-HMAC-SHA256 signature,
    bypassing the synchronous SDK for true async operations.

    Handles sending verification codes for:
    - Account registration
    - SMS login
    - Password reset
    """

    def __init__(self):
        """Initialize SMS service"""
        self._initialized = False
        self._client: Optional[httpx.AsyncClient] = None

        # Validate configuration on init
        if not all([TENCENT_SECRET_ID, TENCENT_SECRET_KEY, SMS_SDK_APP_ID]):
            logger.warning("Tencent SMS credentials not fully configured. SMS service disabled.")
            return

        self._initialized = True
        logger.info("Tencent SMS service initialized (native async mode)")

    @property
    def is_available(self) -> bool:
        """Check if SMS service is available"""
        return self._initialized

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client (lazy initialization)"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(SMS_TIMEOUT_SECONDS),
                http2=True  # Enable HTTP/2 for better performance
            )
        return self._client

    async def close(self):
        """Close HTTP client (call on shutdown)"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _get_template_id(self, purpose: str) -> str:
        """
        Get template ID based on verification purpose

        Args:
            purpose: 'register', 'login', 'reset_password', 'change_phone', or 'alert'

        Returns:
            Template ID string

        Raises:
            SMSServiceError: If template not configured
        """
        templates = {
            "register": SMS_TEMPLATE_REGISTER,
            "login": SMS_TEMPLATE_LOGIN,
            "reset_password": SMS_TEMPLATE_RESET_PASSWORD,
            "change_phone": SMS_TEMPLATE_CHANGE_PHONE or SMS_TEMPLATE_REGISTER,
            "alert": SMS_TEMPLATE_ALERT,
        }

        template_id = templates.get(purpose)
        if not template_id:
            raise SMSServiceError(f"Template not configured for purpose: {purpose}")

        return template_id

    def _format_phone_number(self, phone: str) -> str:
        """
        Format phone number to E.164 standard for China

        Args:
            phone: 11-digit Chinese mobile number (e.g., 13812345678)

        Returns:
            E.164 formatted number (e.g., +8613812345678)
        """
        phone = phone.strip()
        if phone.startswith("+86"):
            return phone
        if phone.startswith("86"):
            return f"+{phone}"
        if phone.startswith("0086"):
            return f"+{phone[2:]}"

        return f"+86{phone}"

    def generate_code(self) -> str:
        """
        Generate random verification code

        Returns:
            6-digit numeric code string
        """
        return ''.join(random.choices(string.digits, k=SMS_CODE_LENGTH))

    def _sign(self, key: bytes, msg: str) -> bytes:
        """HMAC-SHA256 signing helper"""
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _build_authorization(
        self,
        timestamp: int,
        payload: str,
        action: str = "SendSms"
    ) -> str:
        """
        Build TC3-HMAC-SHA256 authorization header

        Implements Tencent Cloud API v3 signature algorithm.
        Reference: https://cloud.tencent.com/document/api/382/52071

        Based on Tencent API Explorer - signs content-type, host, and x-tc-action headers.
        """
        # Date in YYYY-MM-DD format
        date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

        # Step 1: Build canonical request (拼接规范请求串)
        # NOTE: Content-Type in signature must match API Explorer exactly
        # API Explorer uses "application/json" (without charset)
        http_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        ct = "application/json"
        # Headers in canonical format (lowercase values for x-tc-action)
        canonical_headers = (
            f"content-type:{ct}\n"
            f"host:{TENCENT_SMS_HOST}\n"
            f"x-tc-action:{action.lower()}\n"
        )
        signed_headers = "content-type;host;x-tc-action"
        hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        canonical_request = (
            f"{http_method}\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{hashed_payload}"
        )

        # Step 2: Build string to sign (拼接待签名字符串)
        algorithm = "TC3-HMAC-SHA256"
        credential_scope = f"{date}/{TENCENT_SMS_SERVICE}/tc3_request"
        hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()

        string_to_sign = (
            f"{algorithm}\n"
            f"{timestamp}\n"
            f"{credential_scope}\n"
            f"{hashed_canonical}"
        )

        # Step 3: Calculate signature (计算签名)
        secret_date = self._sign(f"TC3{TENCENT_SECRET_KEY}".encode("utf-8"), date)
        secret_service = self._sign(secret_date, TENCENT_SMS_SERVICE)
        secret_signing = self._sign(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing,
            string_to_sign.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # Step 4: Build authorization header (拼接 Authorization)
        authorization = (
            f"{algorithm} "
            f"Credential={TENCENT_SECRET_ID}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        return authorization

    async def send_verification_code(
        self,
        phone: str,
        purpose: str,
        code: Optional[str] = None,
        lang: Language = "en"
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Send SMS verification code (native async)

        Makes direct HTTP call to Tencent SMS API using TC3-HMAC-SHA256 signature.
        Fully async - does not block the event loop.

        Args:
            phone: 11-digit Chinese mobile number
            purpose: 'register', 'login', or 'reset_password'
            code: Optional pre-generated code (will generate if not provided)
            lang: Language code ('zh', 'en', or 'az') for error messages

        Returns:
            Tuple of (success, message, code_if_success)
        """
        if not self.is_available:
            return False, "SMS service not available", None

        # Generate code if not provided
        if not code:
            code = self.generate_code()

        try:
            # Get template ID for purpose
            template_id = self._get_template_id(purpose)

            # Format phone number
            formatted_phone = self._format_phone_number(phone)

            # Build request payload
            # Different templates have different parameter counts:
            # - register (2569002): 1 param [code]
            # - login (2569001): 2 params [code, expiry_minutes]
            # - reset_password (2569003): 1 param [code]
            if purpose == "login":
                template_params = [code, str(SMS_CODE_EXPIRY_MINUTES)]
            else:
                template_params = [code]

            payload = json.dumps({
                "PhoneNumberSet": [formatted_phone],
                "SmsSdkAppId": SMS_SDK_APP_ID,
                "SignName": SMS_SIGN_NAME,
                "TemplateId": template_id,
                "TemplateParamSet": template_params
            })

            # Build headers with signature
            # NOTE: Content-Type must match exactly what's signed in canonical headers
            timestamp = int(time.time())
            action = "SendSms"

            headers = {
                "Authorization": self._build_authorization(timestamp, payload, action),
                "Content-Type": "application/json",
                "Host": TENCENT_SMS_HOST,
                "X-TC-Action": action,
                "X-TC-Timestamp": str(timestamp),
                "X-TC-Version": TENCENT_SMS_VERSION,
                "X-TC-Region": SMS_REGION,
            }

            # Send async HTTP request
            client = await self._get_client()
            response = await client.post(
                TENCENT_SMS_ENDPOINT,
                content=payload,
                headers=headers
            )

            # Check HTTP status code
            if response.status_code != 200:
                response_preview = response.text[:200]
                logger.error(
                    "SMS API returned non-200 status: %s - %s",
                    response.status_code,
                    response_preview
                )
                return False, "SMS service error. Please try again later or contact support.", None

            # Parse response
            try:
                result = response.json()
            except (ValueError, json.JSONDecodeError) as e:
                response_preview = response.text[:200]
                logger.error(
                    "Failed to parse SMS response as JSON: %s - Response: %s",
                    e,
                    response_preview
                )
                return False, "SMS service error. Please try again later or contact support.", None

            if "Response" not in result:
                logger.error("Invalid SMS response structure: %s", result)
                return False, "Invalid SMS response. Please try again later or contact support.", None

            resp_data = result["Response"]

            # Check for API error in Response.Error
            if "Error" in resp_data:
                error_code = resp_data["Error"].get("Code", "Unknown")
                error_msg = resp_data["Error"].get("Message", "Unknown error")
                logger.error("SMS API error: %s - %s", error_code, error_msg)
                return False, self._translate_error_code(error_code, lang), None

            # Check send status in SendStatusSet
            send_status = resp_data.get("SendStatusSet", [])
            if send_status and len(send_status) > 0:
                status = send_status[0]
                if status.get("Code") == "Ok":
                    phone_masked = phone[:3] + "****" + phone[-4:]
                    logger.info("SMS sent successfully to %s for %s", phone_masked, purpose)
                    return True, "Verification code sent successfully", code
                else:
                    error_code = status.get("Code", "Unknown")
                    error_msg = status.get("Message", "Unknown error")
                    logger.error("SMS send failed: %s - %s", error_code, error_msg)
                    return False, self._translate_error_code(error_code, lang), None

            logger.error("Unexpected SMS response structure: %s", resp_data)
            return False, "Unknown SMS response. Please try again later or contact support.", None

        except httpx.TimeoutException:
            logger.error("SMS request timeout")
            return False, "SMS service timeout. Please try again.", None
        except httpx.HTTPError as e:
            logger.error("SMS HTTP error: %s", e)
            return False, "SMS service error. Please try again later.", None
        except SMSServiceError as e:
            logger.error("SMS service error: %s", e)
            return False, str(e), None
        except Exception as e:
            logger.error("Unexpected SMS error: %s", e)
            return False, "SMS service error. Please try again later.", None

    async def send_alert(
        self,
        phones: list[str],
        lang: Language = "zh"
    ) -> Tuple[bool, str]:
        """
        Send SMS alert notification (non-verification code).

        Used for critical system alerts (e.g., service failures, circuit breaker triggered).
        Sends to multiple phone numbers (admin phones).

        Args:
            phones: List of phone numbers (11-digit Chinese mobile numbers)
            lang: Language code ('zh', 'en', or 'az') for error messages

        Returns:
            Tuple of (success, message)
        """
        if not self.is_available:
            return False, "SMS service not available"

        if not phones:
            return False, "No phone numbers provided"

        logger.debug("Sending SMS alert to %d phone(s) (lang: %s)", len(phones), lang)
        try:
            # Get alert template ID
            template_id = self._get_template_id("alert")

            # Format phone numbers
            formatted_phones = [self._format_phone_number(phone) for phone in phones]

            # Alert template typically has no parameters (just the message)
            # Template message: "MindGraph服务器已下线，请尽快核查"
            payload = json.dumps({
                "PhoneNumberSet": formatted_phones,
                "SmsSdkAppId": SMS_SDK_APP_ID,
                "SignName": SMS_SIGN_NAME,
                "TemplateId": template_id,
                "TemplateParamSet": []  # Alert template has no parameters
            })

            # Build headers with signature
            timestamp = int(time.time())
            action = "SendSms"

            headers = {
                "Authorization": self._build_authorization(timestamp, payload, action),
                "Content-Type": "application/json",
                "Host": TENCENT_SMS_HOST,
                "X-TC-Action": action,
                "X-TC-Timestamp": str(timestamp),
                "X-TC-Version": TENCENT_SMS_VERSION,
                "X-TC-Region": SMS_REGION,
            }

            # Send async HTTP request
            client = await self._get_client()
            response = await client.post(
                TENCENT_SMS_ENDPOINT,
                content=payload,
                headers=headers
            )

            # Check HTTP status code
            if response.status_code != 200:
                response_preview = response.text[:200]
                logger.error(
                    "SMS alert API returned non-200 status: %s - %s",
                    response.status_code,
                    response_preview
                )
                return False, "SMS alert service error"

            # Parse response
            try:
                result = response.json()
            except (ValueError, json.JSONDecodeError) as e:
                response_preview = response.text[:200]
                logger.error(
                    "Failed to parse SMS alert response as JSON: %s - Response: %s",
                    e,
                    response_preview
                )
                return False, "SMS alert service error"

            if "Response" not in result:
                logger.error("Invalid SMS alert response structure: %s", result)
                return False, "Invalid SMS alert response"

            resp_data = result["Response"]

            # Check for API error in Response.Error
            if "Error" in resp_data:
                error_code = resp_data["Error"].get("Code", "Unknown")
                error_msg = resp_data["Error"].get("Message", "Unknown error")
                logger.error("SMS alert API error: %s - %s", error_code, error_msg)
                return False, self._translate_error_code(error_code, lang)

            # Check send status in SendStatusSet
            send_status = resp_data.get("SendStatusSet", [])
            success_count = 0
            failed_count = 0

            for status in send_status:
                if status.get("Code") == "Ok":
                    success_count += 1
                else:
                    failed_count += 1
                    error_code = status.get("Code", "Unknown")
                    error_msg = status.get("Message", "Unknown error")
                    phone_number = status.get("PhoneNumber", "unknown")
                    logger.error(
                        "SMS alert send failed for phone: %s - %s",
                        phone_number,
                        error_msg
                    )

            if success_count > 0:
                logger.info(
                    "SMS alert sent successfully to %d/%d admin phone(s)",
                    success_count,
                    len(phones)
                )
                return True, f"Alert sent to {success_count} admin phone(s)"

            logger.error("SMS alert failed for all %d phone(s)", len(phones))
            return False, "SMS alert failed for all recipients"

        except httpx.TimeoutException:
            logger.error("SMS alert request timeout")
            return False, "SMS alert timeout"
        except httpx.HTTPError as e:
            logger.error("SMS alert HTTP error: %s", e)
            return False, "SMS alert HTTP error"
        except SMSServiceError as e:
            logger.error("SMS alert service error: %s", e)
            return False, str(e)
        except Exception as e:
            logger.error("Unexpected SMS alert error: %s", e, exc_info=True)
            return False, "SMS alert service error"

    async def send_notification(
        self,
        phones: list[str],
        template_id: str,
        template_params: Optional[list[str]] = None,
        lang: Language = "zh"
    ) -> Tuple[bool, str]:
        """
        Send SMS notification with custom template ID.

        Used for custom notifications (e.g., startup notifications, custom alerts).
        Sends to multiple phone numbers.

        Args:
            phones: List of phone numbers (11-digit Chinese mobile numbers)
            template_id: Tencent SMS template ID
            template_params: Optional list of template parameters (empty list if template has no params)
            lang: Language code ('zh', 'en', or 'az') for error messages

        Returns:
            Tuple of (success, message)
        """
        if not self.is_available:
            return False, "SMS service not available"

        if not phones:
            return False, "No phone numbers provided"

        if not template_id:
            return False, "Template ID not provided"

        logger.debug(
            "Sending SMS notification to %d phone(s) using template %s (lang: %s)",
            len(phones),
            template_id,
            lang
        )
        try:
            # Format phone numbers
            formatted_phones = [self._format_phone_number(phone) for phone in phones]

            # Use empty list if template_params is None
            if template_params is None:
                template_params = []

            payload = json.dumps({
                "PhoneNumberSet": formatted_phones,
                "SmsSdkAppId": SMS_SDK_APP_ID,
                "SignName": SMS_SIGN_NAME,
                "TemplateId": template_id,
                "TemplateParamSet": template_params
            })

            # Build headers with signature
            timestamp = int(time.time())
            action = "SendSms"

            headers = {
                "Authorization": self._build_authorization(timestamp, payload, action),
                "Content-Type": "application/json",
                "Host": TENCENT_SMS_HOST,
                "X-TC-Action": action,
                "X-TC-Timestamp": str(timestamp),
                "X-TC-Version": TENCENT_SMS_VERSION,
                "X-TC-Region": SMS_REGION,
            }

            # Send async HTTP request
            client = await self._get_client()
            response = await client.post(
                TENCENT_SMS_ENDPOINT,
                content=payload,
                headers=headers
            )

            # Check HTTP status code
            if response.status_code != 200:
                response_preview = response.text[:200]
                logger.error(
                    "SMS notification API returned non-200 status: %s - %s",
                    response.status_code,
                    response_preview
                )
                return False, "SMS notification service error"

            # Parse response
            try:
                result = response.json()
            except (ValueError, json.JSONDecodeError) as e:
                response_preview = response.text[:200]
                logger.error(
                    "Failed to parse SMS notification response as JSON: %s - Response: %s",
                    e,
                    response_preview
                )
                return False, "SMS notification service error"

            if "Response" not in result:
                logger.error("Invalid SMS notification response structure: %s", result)
                return False, "Invalid SMS notification response"

            resp_data = result["Response"]

            # Check for API error in Response.Error
            if "Error" in resp_data:
                error_code = resp_data["Error"].get("Code", "Unknown")
                error_msg = resp_data["Error"].get("Message", "Unknown error")
                logger.error("SMS notification API error: %s - %s", error_code, error_msg)
                return False, self._translate_error_code(error_code, lang)

            # Check send status in SendStatusSet
            send_status = resp_data.get("SendStatusSet", [])
            success_count = 0
            failed_count = 0

            for status in send_status:
                if status.get("Code") == "Ok":
                    success_count += 1
                else:
                    failed_count += 1
                    error_code = status.get("Code", "Unknown")
                    error_msg = status.get("Message", "Unknown error")
                    phone_number = status.get("PhoneNumber", "unknown")
                    logger.error(
                        "SMS notification send failed for phone: %s - %s",
                        phone_number,
                        error_msg
                    )

            if success_count > 0:
                logger.info(
                    "SMS notification sent successfully to %d/%d phone(s)",
                    success_count,
                    len(phones)
                )
                return True, f"Notification sent to {success_count} phone(s)"

            logger.error("SMS notification failed for all %d phone(s)", len(phones))
            return False, "SMS notification failed for all recipients"

        except httpx.TimeoutException:
            logger.error("SMS notification request timeout")
            return False, "SMS notification timeout"
        except httpx.HTTPError as e:
            logger.error("SMS notification HTTP error: %s", e)
            return False, "SMS notification HTTP error"
        except SMSServiceError as e:
            logger.error("SMS notification service error: %s", e)
            return False, str(e)
        except Exception as e:
            logger.error("Unexpected SMS notification error: %s", e, exc_info=True)
            return False, "SMS notification service error"

    def _translate_error_code(self, code: str, lang: Language = "en") -> str:
        """
        Translate Tencent SMS error codes to user-friendly messages using Messages system

        Comprehensive error handling for all Tencent Cloud SMS API error codes.
        Errors are categorized into:
        - User-actionable: Rate limits, invalid input (user can retry/fix)
        - Configuration: Signature, template issues (admin action needed)
        - System: Timeout, internal errors (retry or contact support)

        Args:
            code: Tencent SMS error code
            lang: Language code ('zh', 'en', or 'az')

        Returns:
            User-friendly error message in the specified language
        """
        # Map error codes to Messages system keys
        error_code_map = {
            # ====================================================================
            # FailedOperation - Operation Failed Errors
            # ====================================================================
            "FailedOperation.ContainSensitiveWord": "sms_error_contain_sensitive_word",
            "FailedOperation.FailResolvePacket": "sms_error_fail_resolve_packet",
            "FailedOperation.InsufficientBalanceInSmsPackage": "sms_error_insufficient_balance",
            "FailedOperation.JsonParseFail": "sms_error_fail_resolve_packet",
            "FailedOperation.MarketingSendTimeConstraint": "sms_error_marketing_time_constraint",
            "FailedOperation.PhoneNumberInBlacklist": "sms_error_phone_in_blacklist",
            "FailedOperation.SignatureIncorrectOrUnapproved": "sms_error_signature_config",
            "FailedOperation.TemplateIncorrectOrUnapproved": "sms_error_template_config",
            "FailedOperation.TemplateParamSetNotMatchApprovedTemplate": "sms_error_template_params_mismatch",
            "FailedOperation.TemplateUnapprovedOrNotExist": "sms_error_template_unapproved",

            # ====================================================================
            # InternalError - Internal Server Errors
            # ====================================================================
            "InternalError.OtherError": "sms_error_internal_other",
            "InternalError.RequestTimeException": "sms_error_request_time",
            "InternalError.RestApiInterfaceNotExist": "sms_error_api_interface",
            "InternalError.SendAndRecvFail": "sms_error_timeout",
            "InternalError.SigFieldMissing": "sms_error_auth_failed",
            "InternalError.SigVerificationFail": "sms_error_auth_failed",
            "InternalError.Timeout": "sms_error_timeout",
            "InternalError.UnknownError": "sms_error_unknown",

            # ====================================================================
            # InvalidParameterValue - Invalid Parameter Errors
            # ====================================================================
            "InvalidParameterValue.ContentLengthLimit": "sms_error_content_too_long",
            "InvalidParameterValue.IncorrectPhoneNumber": "sms_error_invalid_phone",
            "InvalidParameterValue.ProhibitedUseUrlInTemplateParameter": "sms_error_url_prohibited",
            "InvalidParameterValue.SdkAppIdNotExist": "sms_error_sdk_app_id_not_exist",
            "InvalidParameterValue.TemplateParameterFormatError": "sms_error_template_param_format",
            "InvalidParameterValue.TemplateParameterLengthLimit": "sms_error_template_param_length",

            # ====================================================================
            # LimitExceeded - Rate Limit Errors
            # ====================================================================
            "LimitExceeded.AppCountryOrRegionDailyLimit": "sms_error_daily_limit_country",
            "LimitExceeded.AppCountryOrRegionInBlacklist": "sms_error_country_restricted",
            "LimitExceeded.AppDailyLimit": "sms_error_daily_limit",
            "LimitExceeded.AppGlobalDailyLimit": "sms_error_international_daily_limit",
            "LimitExceeded.AppMainlandChinaDailyLimit": "sms_error_mainland_daily_limit",
            "LimitExceeded.DailyLimit": "sms_error_daily_limit",
            "LimitExceeded.DeliveryFrequencyLimit": "sms_error_frequency_limit",
            "LimitExceeded.PhoneNumberCountLimit": "sms_error_phone_count_limit",
            "LimitExceeded.PhoneNumberDailyLimit": "sms_error_phone_daily_limit",
            "LimitExceeded.PhoneNumberOneHourLimit": "sms_error_phone_hourly_limit",
            "LimitExceeded.PhoneNumberSameContentDailyLimit": "sms_error_phone_same_content_daily",
            "LimitExceeded.PhoneNumberThirtySecondLimit": "sms_error_phone_thirty_second_limit",

            # ====================================================================
            # MissingParameter - Missing Parameter Errors
            # ====================================================================
            "MissingParameter.EmptyPhoneNumberSet": "sms_error_empty_phone_list",

            # ====================================================================
            # UnauthorizedOperation - Authorization Errors
            # ====================================================================
            "UnauthorizedOperation.IndividualUserMarketingSmsPermissionDeny": "sms_error_marketing_permission_denied",
            "UnauthorizedOperation.RequestIpNotInWhitelist": "sms_error_ip_not_whitelisted",
            "UnauthorizedOperation.RequestPermissionDeny": "sms_error_permission_denied",
            "UnauthorizedOperation.SdkAppIdIsDisabled": "sms_error_service_disabled",
            "UnauthorizedOperation.ServiceSuspendDueToArrears": "sms_error_service_suspended",
            "UnauthorizedOperation.SmsSdkAppIdVerifyFail": "sms_error_auth_verify_failed",

            # ====================================================================
            # UnsupportedOperation - Unsupported Operation Errors
            # ====================================================================
            "UnsupportedOperation": "sms_error_operation_not_supported",
            "UnsupportedOperation.ChineseMainlandTemplateToGlobalPhone": "sms_error_template_mismatch_domestic",
            "UnsupportedOperation.ContainDomesticAndInternationalPhoneNumber": "sms_error_mixed_phone_types",
            "UnsupportedOperation.GlobalTemplateToChineseMainlandPhone": "sms_error_template_mismatch_international",
            "UnsupportedOperation.UnsupportedRegion": "sms_error_region_not_supported",

            # ====================================================================
            # Legacy/Alternative Error Code Formats (for backward compatibility)
            # ====================================================================
            "FailedOperation.SignatureIncorrect": "sms_error_signature_config",
            "FailedOperation.TemplateIncorrect": "sms_error_template_config",
            "AuthFailure.SecretIdNotFound": "sms_error_auth_verify_failed",
            "AuthFailure.SignatureFailure": "sms_error_auth_verify_failed",
        }

        # Get Messages key for this error code
        message_key = error_code_map.get(code)
        if message_key:
            return Messages.error(message_key, lang)

        # Fallback for unknown error codes
        return Messages.error("sms_error_generic", lang, code)
