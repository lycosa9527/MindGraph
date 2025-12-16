"""
SMS Middleware
==============

Unified SMS service and middleware for Tencent Cloud SMS API.
Provides native async HTTP calls with TC3-HMAC-SHA256 signature,
bypassing the synchronous Tencent SDK entirely.

Features:
- Native async HTTP calls via httpx
- Rate limiting (concurrent request limits)
- QPM (Queries Per Minute) limiting
- Error handling
- Performance tracking

@author lycosa9527
@made_by MindSpring Team
"""

import os
import json
import random
import string
import hashlib
import hmac
import time
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from contextlib import asynccontextmanager

import httpx

from services.rate_limiter import DashscopeRateLimiter
from services.performance_tracker import performance_tracker
from config.settings import config
from models.messages import Messages, Language

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
    pass


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
            purpose: 'register', 'login', or 'reset_password'
            
        Returns:
            Template ID string
            
        Raises:
            SMSServiceError: If template not configured
        """
        templates = {
            "register": SMS_TEMPLATE_REGISTER,
            "login": SMS_TEMPLATE_LOGIN,
            "reset_password": SMS_TEMPLATE_RESET_PASSWORD,
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
                "Content-Type": "application/json",  # Must match canonical headers (API Explorer format)
                "Host": TENCENT_SMS_HOST,
                "X-TC-Action": action,
                "X-TC-Timestamp": str(timestamp),  # httpx accepts string, API Explorer uses int as string
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
                logger.error(f"SMS API returned non-200 status: {response.status_code} - {response.text[:200]}")
                return False, "SMS service error. Please try again later or contact support.", None
            
            # Parse response
            try:
                result = response.json()
            except (ValueError, json.JSONDecodeError) as e:
                logger.error(f"Failed to parse SMS response as JSON: {e} - Response: {response.text[:200]}")
                return False, "SMS service error. Please try again later or contact support.", None
            
            if "Response" not in result:
                logger.error(f"Invalid SMS response structure: {result}")
                return False, "Invalid SMS response. Please try again later or contact support.", None
            
            resp_data = result["Response"]
            
            # Check for API error in Response.Error
            if "Error" in resp_data:
                error_code = resp_data["Error"].get("Code", "Unknown")
                error_msg = resp_data["Error"].get("Message", "Unknown error")
                logger.error(f"SMS API error: {error_code} - {error_msg}")
                return False, self._translate_error_code(error_code, lang), None
            
            # Check send status in SendStatusSet
            send_status = resp_data.get("SendStatusSet", [])
            if send_status and len(send_status) > 0:
                status = send_status[0]
                if status.get("Code") == "Ok":
                    logger.info(f"SMS sent successfully to {phone[:3]}****{phone[-4:]} for {purpose}")
                    return True, "Verification code sent successfully", code
                else:
                    error_code = status.get("Code", "Unknown")
                    error_msg = status.get("Message", "Unknown error")
                    logger.error(f"SMS send failed: {error_code} - {error_msg}")
                    return False, self._translate_error_code(error_code, lang), None
            
            logger.error(f"Unexpected SMS response structure: {resp_data}")
            return False, "Unknown SMS response. Please try again later or contact support.", None
            
        except httpx.TimeoutException:
            logger.error("SMS request timeout")
            return False, "SMS service timeout. Please try again.", None
        except httpx.HTTPError as e:
            logger.error(f"SMS HTTP error: {e}")
            return False, "SMS service error. Please try again later.", None
        except SMSServiceError as e:
            logger.error(f"SMS service error: {e}")
            return False, str(e), None
        except Exception as e:
            logger.error(f"Unexpected SMS error: {e}")
            return False, "SMS service error. Please try again later.", None
    
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


class SMSMiddleware:
    """
    Middleware for SMS service requests.
    
    Provides rate limiting, error handling, and performance tracking
    for SMS API calls to Tencent Cloud.
    """
    
    def __init__(
        self,
        max_concurrent_requests: Optional[int] = None,
        qpm_limit: Optional[int] = None,
        enable_rate_limiting: bool = True,
        enable_error_handling: bool = True,
        enable_performance_tracking: bool = True
    ):
        """
        Initialize SMS middleware.
        
        Args:
            max_concurrent_requests: Max concurrent SMS API requests (None = use config)
            qpm_limit: Queries per minute limit (None = use config)
            enable_rate_limiting: Enable rate limiting
            enable_error_handling: Enable error handling
            enable_performance_tracking: Enable performance metrics tracking
        """
        self.max_concurrent_requests = max_concurrent_requests or config.SMS_MAX_CONCURRENT_REQUESTS
        self.qpm_limit = qpm_limit or config.SMS_QPM_LIMIT
        # Enable rate limiting only if both parameter and config are True
        if enable_rate_limiting is None:
            self.enable_rate_limiting = config.SMS_RATE_LIMITING_ENABLED
        else:
            self.enable_rate_limiting = enable_rate_limiting and config.SMS_RATE_LIMITING_ENABLED
        self.enable_error_handling = enable_error_handling
        self.enable_performance_tracking = enable_performance_tracking
        
        # Initialize internal SMS service
        self._sms_service = SMSService()
        
        # Track active requests
        self._active_requests = 0
        self._request_lock = asyncio.Lock()
        
        # Create SMS-specific rate limiter
        self.rate_limiter = None
        if self.enable_rate_limiting:
            self.rate_limiter = DashscopeRateLimiter(
                qpm_limit=self.qpm_limit,
                concurrent_limit=self.max_concurrent_requests,
                enabled=True
            )
            logger.info(
                f"[SMSMiddleware] Initialized with rate limiting: "
                f"QPM={self.qpm_limit}, Concurrent={self.max_concurrent_requests}"
            )
        else:
            logger.info(
                f"[SMSMiddleware] Initialized without rate limiting: "
                f"Concurrent={self.max_concurrent_requests}"
            )
    
    @property
    def is_available(self) -> bool:
        """Check if SMS service is available"""
        return self._sms_service.is_available
    
    def generate_code(self) -> str:
        """Generate random verification code"""
        return self._sms_service.generate_code()
    
    @asynccontextmanager
    async def request_context(
        self,
        phone: str,
        purpose: str,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None
    ):
        """
        Context manager for SMS request lifecycle.
        
        Provides rate limiting, request tracking, and error handling.
        
        Args:
            phone: Phone number (masked in logs)
            purpose: SMS purpose ('register', 'login', 'reset_password')
            user_id: User ID for tracking
            organization_id: Organization ID for tracking
            
        Yields:
            Dict with request metadata and tracking info
            
        Example:
            async with sms_middleware.request_context(phone, purpose) as ctx:
                success, msg, code = await sms_middleware.send_verification_code(...)
        """
        request_start_time = time.time()
        request_id = f"sms_{purpose}_{int(time.time() * 1000)}"
        masked_phone = f"{phone[:3]}****{phone[-4:]}" if len(phone) >= 7 else "****"
        
        # Apply rate limiting if enabled
        rate_limit_context = None
        if self.enable_rate_limiting and self.rate_limiter:
            try:
                rate_limit_context = await self.rate_limiter.__aenter__()
            except Exception as e:
                logger.warning(f"[SMSMiddleware] Rate limiter acquisition failed: {e}")
                if self.enable_error_handling:
                    raise SMSServiceError(
                        f"SMS service temporarily unavailable due to rate limiting. "
                        f"Please try again in a moment."
                    ) from e
                raise
        
        # Track active requests (for monitoring, even without rate limiter)
        async with self._request_lock:
            self._active_requests += 1
            logger.debug(
                f"[SMSMiddleware] Request {request_id} started "
                f"({self._active_requests}/{self.max_concurrent_requests} active) "
                f"for {masked_phone} ({purpose})"
            )
        
        try:
            # Prepare context for request
            ctx = {
                'request_id': request_id,
                'phone': phone,
                'masked_phone': masked_phone,
                'purpose': purpose,
                'user_id': user_id,
                'organization_id': organization_id,
                'start_time': request_start_time
            }
            
            yield ctx
            
            # Track successful request
            duration = time.time() - request_start_time
            if self.enable_performance_tracking:
                self._track_performance(
                    duration=duration,
                    success=True,
                    error=None,
                    purpose=purpose
                )
            
            logger.debug(
                f"[SMSMiddleware] Request {request_id} completed successfully "
                f"in {duration:.2f}s for {masked_phone}"
            )
        
        except Exception as e:
            # Track failed request
            duration = time.time() - request_start_time
            if self.enable_performance_tracking:
                self._track_performance(
                    duration=duration,
                    success=False,
                    error=str(e),
                    purpose=purpose
                )
            
            logger.error(
                f"[SMSMiddleware] Request {request_id} failed "
                f"after {duration:.2f}s for {masked_phone}: {e}",
                exc_info=True
            )
            
            # Apply error handling if enabled
            if self.enable_error_handling:
                # Re-raise with SMS-specific error context
                raise SMSServiceError(f"SMS request failed: {e}") from e
            else:
                raise
        
        finally:
            # Release rate limiter
            if rate_limit_context:
                try:
                    await self.rate_limiter.__aexit__(None, None, None)
                except Exception as e:
                    logger.debug(f"[SMSMiddleware] Error releasing rate limiter: {e}")
            
            # Decrement active requests
            async with self._request_lock:
                self._active_requests -= 1
                logger.debug(
                    f"[SMSMiddleware] Request {request_id} completed "
                    f"({self._active_requests}/{self.max_concurrent_requests} active)"
                )
    
    async def send_verification_code(
        self,
        phone: str,
        purpose: str,
        code: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        lang: Language = "en"
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Send SMS verification code with middleware (recommended method).
        
        This method wraps the SMS service call with rate limiting and tracking.
        
        Args:
            phone: 11-digit Chinese mobile number
            purpose: 'register', 'login', or 'reset_password'
            code: Optional pre-generated code (will generate if not provided)
            user_id: User ID for tracking
            organization_id: Organization ID for tracking
            lang: Language code ('zh', 'en', or 'az') for error messages
            
        Returns:
            Tuple of (success, message, code_if_success)
        """
        async with self.request_context(phone, purpose, user_id, organization_id):
            return await self._sms_service.send_verification_code(phone, purpose, code, lang)
    
    def _track_performance(
        self,
        duration: float,
        success: bool,
        error: Optional[str] = None,
        purpose: Optional[str] = None
    ):
        """Track performance metrics for SMS requests."""
        try:
            # Use 'sms' as model name, append purpose for better tracking
            model_name = f"sms-{purpose}" if purpose else "sms"
            performance_tracker.record_request(
                model=model_name,
                duration=duration,
                success=success,
                error=error
            )
        except Exception as e:
            logger.debug(f"[SMSMiddleware] Performance tracking failed (non-critical): {e}")
    
    def get_active_requests(self) -> int:
        """Get number of active SMS requests."""
        return self._active_requests
    
    def get_max_requests(self) -> int:
        """Get maximum concurrent SMS requests."""
        return self.max_concurrent_requests
    
    def get_rate_limiter_stats(self) -> Optional[Dict[str, Any]]:
        """Get rate limiter statistics if available."""
        if self.rate_limiter:
            return self.rate_limiter.get_stats()
        return None
    
    async def close(self):
        """Close SMS service (call on shutdown)"""
        await self._sms_service.close()


# Singleton instance for SMS middleware
_sms_middleware: Optional[SMSMiddleware] = None


def get_sms_middleware() -> SMSMiddleware:
    """
    Get singleton SMS middleware instance.
    
    Returns:
        SMSMiddleware instance
    """
    global _sms_middleware
    if _sms_middleware is None:
        _sms_middleware = SMSMiddleware()
    return _sms_middleware


def get_sms_service() -> SMSMiddleware:
    """
    Get SMS service (backward compatibility - returns middleware).
    
    The middleware now contains the SMS service functionality.
    Use get_sms_middleware() for new code.
    
    Returns:
        SMSMiddleware instance (which includes SMS service)
    """
    return get_sms_middleware()


async def shutdown_sms_service():
    """
    Shutdown SMS service (call on app shutdown)
    
    Closes the httpx async client properly.
    """
    global _sms_middleware
    if _sms_middleware is not None:
        await _sms_middleware.close()
        _sms_middleware = None
        logger.info("SMS service shut down")
