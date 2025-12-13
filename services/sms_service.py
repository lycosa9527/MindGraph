"""
SMS Service for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Tencent Cloud SMS integration for account verification.
Supports: registration, login, and password reset.

Uses native async HTTP calls via httpx for high concurrency,
bypassing the synchronous Tencent SDK entirely.
"""

import os
import json
import random
import string
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

import httpx

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

# Rate limiting configuration
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
        code: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Send SMS verification code (native async)
        
        Makes direct HTTP call to Tencent SMS API using TC3-HMAC-SHA256 signature.
        Fully async - does not block the event loop.
        
        Args:
            phone: 11-digit Chinese mobile number
            purpose: 'register', 'login', or 'reset_password'
            code: Optional pre-generated code (will generate if not provided)
            
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
            
            # Parse response
            result = response.json()
            
            if "Response" not in result:
                logger.error(f"Invalid SMS response: {result}")
                return False, "Invalid SMS response", None
            
            resp_data = result["Response"]
            
            # Check for API error
            if "Error" in resp_data:
                error_code = resp_data["Error"].get("Code", "Unknown")
                error_msg = resp_data["Error"].get("Message", "Unknown error")
                logger.error(f"SMS API error: {error_code} - {error_msg}")
                return False, self._translate_error_code(error_code), None
            
            # Check send status
            send_status = resp_data.get("SendStatusSet", [])
            if send_status and len(send_status) > 0:
                status = send_status[0]
                if status.get("Code") == "Ok":
                    logger.info(f"SMS sent successfully to {phone[:3]}****{phone[-4:]} for {purpose}")
                    return True, "Verification code sent successfully", code
                else:
                    error_code = status.get("Code", "Unknown")
                    logger.error(f"SMS send failed: {error_code} - {status.get('Message')}")
                    return False, self._translate_error_code(error_code), None
            
            return False, "Unknown SMS response", None
            
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
    
    def _translate_error_code(self, code: str) -> str:
        """
        Translate Tencent SMS error codes to user-friendly messages
        
        Args:
            code: Tencent SMS error code
            
        Returns:
            User-friendly error message
        """
        error_messages = {
            "LimitExceeded.PhoneNumberDailyLimit": "Daily SMS limit reached for this number",
            "LimitExceeded.PhoneNumberThirtySecondLimit": "Please wait 30 seconds before requesting again",
            "LimitExceeded.PhoneNumberOneHourLimit": "Hourly SMS limit reached for this number",
            "InvalidParameterValue.IncorrectPhoneNumber": "Invalid phone number format",
            "FailedOperation.PhoneNumberInBlacklist": "Phone number is blocked",
            "FailedOperation.SignatureIncorrect": "SMS signature configuration error",
            "FailedOperation.TemplateIncorrect": "SMS template configuration error",
            "FailedOperation.InsufficientBalanceInSmsPackage": "SMS service balance insufficient",
            "AuthFailure.SecretIdNotFound": "SMS service authentication error",
            "AuthFailure.SignatureFailure": "SMS service signature error",
        }
        
        return error_messages.get(code, f"SMS send failed: {code}")


# Singleton instance
_sms_service: Optional[SMSService] = None


def get_sms_service() -> SMSService:
    """
    Get singleton SMS service instance
    
    Returns:
        SMSService instance
    """
    global _sms_service
    if _sms_service is None:
        _sms_service = SMSService()
    return _sms_service


async def shutdown_sms_service():
    """
    Shutdown SMS service (call on app shutdown)
    
    Closes the httpx async client properly.
    """
    global _sms_service
    if _sms_service is not None:
        await _sms_service.close()
        _sms_service = None
        logger.info("SMS service shut down")
