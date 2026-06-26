"""Authentication and SMS Verification Request Models.

Pydantic models for validating authentication and SMS verification API requests.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from services.auth.quick_register_redis import WORKSHOP_MAX_USES_CAP
from utils.prompt_output_languages import is_prompt_output_language
from utils.ui_languages import UI_LANGUAGE_CODES

# Common/breached passwords rejected outright (NIST SP 800-63B recommends a
# blocklist check rather than forced composition rules).
_COMMON_WEAK_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "12345678",
        "123456789",
        "1234567890",
        "11111111",
        "00000000",
        "qwerty123",
        "abcd1234",
        "iloveyou",
        "admin123",
        "passw0rd",
        "welcome1",
        "1q2w3e4r",
    }
)


def validate_password_strength(value: str) -> str:
    """Reject trivially weak passwords (length is enforced separately by Field).

    NIST 800-63B aligned: length + common-password blocklist, no composition
    requirements. Avoids overly aggressive rules that harm usability.
    """
    candidate = value or ""
    if candidate.lower() in _COMMON_WEAK_PASSWORDS:
        raise ValueError("Password is too common. Choose a less predictable password.")
    if len(set(candidate)) == 1:
        raise ValueError("Password must not be a single repeated character.")
    return value


StrongPassword = Annotated[str, AfterValidator(validate_password_strength)]


# ============================================================================
# AUTHENTICATION REQUEST MODELS
# ============================================================================


class RegisterRequest(BaseModel):
    """Request model for user registration"""

    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    password: StrongPassword = Field(..., min_length=8, description="Password (min 8 characters)")
    name: str = Field(
        ...,
        min_length=2,
        description="Teacher's name (required, min 2 chars, no numbers)",
    )
    invitation_code: str = Field(
        ...,
        description=("Invitation code for registration (automatically binds to school)"),
    )
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith("1"):
            raise ValueError(
                "Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate name has no numbers"""
        if len(v) < 2:
            raise ValueError(f"Name is too short ({len(v)} character(s)). Must be at least 2 characters.")
        if any(char.isdigit() for char in v):
            raise ValueError("Name cannot contain numbers. Please enter your name using letters only.")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "13812345678",
                "password": "Teacher123!",
                "name": "Zhang Wei",
                "invitation_code": "DEM-9K2",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session",
            }
        }
    )


class RegisterOverseasRequest(BaseModel):
    """Email registration outside mainland China (GeoIP not CN)."""

    email: str = Field(..., max_length=254, description="Email address for overseas registration")
    password: StrongPassword = Field(..., min_length=8, description="Password (min 8 characters)")
    name: str = Field(
        ...,
        min_length=2,
        description="Display name (min 2 chars, no numbers)",
    )
    email_code: str = Field(..., min_length=6, max_length=6, description="6-digit email verification code")
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")
    outside_mainland_acknowledged: bool = Field(
        ...,
        description="Must be true: user acknowledges overseas email registration terms",
    )

    @field_validator("email")
    @classmethod
    def strip_email(cls, value: str) -> str:
        """Trim surrounding whitespace from the email."""
        return value.strip()

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject names shorter than two characters or containing digits."""
        if len(value) < 2:
            raise ValueError("Name must be at least 2 characters.")
        if any(char.isdigit() for char in value):
            raise ValueError("Name cannot contain numbers.")
        return value

    @field_validator("email_code")
    @classmethod
    def validate_email_code(cls, value: str) -> str:
        """Ensure the email verification code is exactly 6 digits."""
        value = value.strip()
        if len(value) != 6 or not value.isdigit():
            raise ValueError("Email verification code must be 6 digits.")
        return value


class LoginRequest(BaseModel):
    """Request model for user login (phone or email)."""

    phone: Optional[str] = Field(None, max_length=64, description="11-digit Chinese mobile")
    email: Optional[str] = Field(None, max_length=254, description="Account email (overseas registration)")
    password: str = Field(..., description="User password")
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")

    @model_validator(mode="after")
    def exactly_one_login_identifier(self) -> LoginRequest:
        """Require exactly one of phone or email to be provided."""
        data = self.model_dump()
        phone_val = data.get("phone")
        email_val = data.get("email")
        phone_set = bool(phone_val and str(phone_val).strip())
        email_set = bool(email_val and str(email_val).strip())
        if phone_set == email_set:
            raise ValueError("Provide exactly one of phone or email")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "13812345678",
                "password": "Teacher123!",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session",
            }
        }
    )


class PasskeyVerifyRequest(BaseModel):
    """Request body for 6-digit passkey verification (Bayi passkey login, public dashboard)."""

    passkey: str = Field(..., min_length=6, max_length=6, description="6-digit passkey")

    @field_validator("passkey")
    @classmethod
    def validate_passkey(cls, value):
        """Validate 6-digit passkey"""
        if not value.isdigit():
            raise ValueError("Passkey must contain only digits")
        if len(value) != 6:
            raise ValueError("Passkey must be exactly 6 digits")
        return value

    model_config = ConfigDict(json_schema_extra={"example": {"passkey": "888888"}})


# ============================================================================
# SMS VERIFICATION REQUEST MODELS
# ============================================================================


class SendSMSCodeRequest(BaseModel):
    """Request model for sending SMS verification code"""

    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    purpose: str = Field(..., description="Purpose: 'register', 'login', or 'reset_password'")
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith("1"):
            raise ValueError(
                "Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v):
        """Validate SMS purpose"""
        valid_purposes = ["register", "login", "reset_password", "change_phone"]
        if v not in valid_purposes:
            raise ValueError(f"Purpose must be one of: {', '.join(valid_purposes)}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "13812345678",
                "purpose": "register",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session",
            }
        }
    )


class SendSMSCodeSimpleRequest(BaseModel):
    """Simplified request model for purpose-specific SMS endpoints."""

    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith("1"):
            raise ValueError(
                "Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1."
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "13812345678",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session",
            }
        }
    )


class VerifySMSCodeRequest(BaseModel):
    """Request model for verifying SMS code (standalone verification)"""

    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit SMS verification code")
    purpose: str = Field(..., description="Purpose: 'register', 'login', or 'reset_password'")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith("1"):
            raise ValueError(
                "Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError(
                "SMS verification code must contain only digits. Please enter the 6-digit code sent to your phone."
            )
        if len(v) != 6:
            raise ValueError(f"SMS verification code must be exactly 6 digits. You entered {len(v)} digit(s).")
        return v

    model_config = ConfigDict(
        json_schema_extra={"example": {"phone": "13812345678", "code": "123456", "purpose": "register"}}
    )


# ============================================================================
# EMAIL VERIFICATION REQUEST MODELS (Tencent SES)
# ============================================================================


class SendEmailCodeRequest(BaseModel):
    """Request model for sending email verification code (SES)."""

    email: str = Field(..., max_length=254, description="Recipient email address")
    purpose: str = Field(
        ...,
        description=(
            "Purpose: register (overseas), reset_password (email reset), or login (email OTP login); "
            "narrowed to implemented flows."
        ),
    )
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")

    @field_validator("email")
    @classmethod
    def strip_email(cls, v: str) -> str:
        """Trim surrounding whitespace from the email."""
        return v.strip()

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        """Restrict purpose to register/reset_password/login."""
        valid = ["register", "reset_password", "login"]
        if v not in valid:
            raise ValueError(f"Purpose must be one of: {', '.join(valid)}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "purpose": "register",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session",
            }
        }
    )


class VerifyEmailCodeRequest(BaseModel):
    """Request model for verifying email code (standalone)."""

    email: str = Field(..., max_length=254, description="Recipient email address")
    code: str = Field(..., min_length=1, max_length=6, description="6-digit verification code")
    purpose: str = Field(..., description="Purpose: register, reset_password, or login")

    @field_validator("email")
    @classmethod
    def strip_email(cls, v: str) -> str:
        """Trim surrounding whitespace from the email."""
        return v.strip()

    @field_validator("code")
    @classmethod
    def strip_code(cls, v: str) -> str:
        """Trim surrounding whitespace from the code."""
        return v.strip()

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        """Restrict purpose to register/reset_password/login."""
        valid = ["register", "reset_password", "login"]
        if v not in valid:
            raise ValueError(f"Purpose must be one of: {', '.join(valid)}")
        return v

    model_config = ConfigDict(
        json_schema_extra={"example": {"email": "user@example.com", "code": "123456", "purpose": "register"}}
    )


class ResetPasswordWithEmailRequest(BaseModel):
    """Request model for password reset with email verification code."""

    email: str = Field(..., max_length=254, description="Account email address")
    email_code: str = Field(..., min_length=6, max_length=6, description="6-digit email verification code")
    new_password: StrongPassword = Field(..., min_length=8, description="New password (min 8 characters)")

    @field_validator("email")
    @classmethod
    def strip_email(cls, v: str) -> str:
        """Trim surrounding whitespace from the email."""
        return v.strip()

    @field_validator("email_code")
    @classmethod
    def validate_email_code(cls, v: str) -> str:
        """Ensure the email verification code is exactly 6 digits."""
        v = v.strip()
        if len(v) != 6 or not v.isdigit():
            raise ValueError("Email verification code must be exactly 6 digits.")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@university.edu",
                "email_code": "123456",
                "new_password": "NewPassword123!",
            }
        }
    )


class RegisterWithSMSRequest(BaseModel):
    """Request model for registration with SMS verification"""

    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    password: StrongPassword = Field(..., min_length=8, description="Password (min 8 characters)")
    name: str = Field(
        ...,
        min_length=2,
        description="Teacher's name (required, min 2 chars, no numbers)",
    )
    invitation_code: str = Field(..., description="Invitation code for registration")
    sms_code: str = Field(..., min_length=6, max_length=6, description="6-digit SMS verification code")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith("1"):
            raise ValueError(
                "Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate name has no numbers"""
        if len(v) < 2:
            raise ValueError(f"Name is too short ({len(v)} character(s)). Must be at least 2 characters.")
        if any(char.isdigit() for char in v):
            raise ValueError("Name cannot contain numbers. Please enter your name using letters only.")
        return v

    @field_validator("sms_code")
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError(
                "SMS verification code must contain only digits. Please enter the 6-digit code sent to your phone."
            )
        if len(v) != 6:
            raise ValueError(f"SMS verification code must be exactly 6 digits. You entered {len(v)} digit(s).")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "13812345678",
                "password": "Teacher123!",
                "name": "Zhang Wei",
                "invitation_code": "DEM-9K2",
                "sms_code": "123456",
            }
        }
    )


class RegisterQuickRequest(BaseModel):
    """Registration via quick register: phone, rotating 6-digit room code, and server-minted token."""

    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    quick_reg_token: str = Field(..., min_length=20, max_length=512, description="Opaque quick-registration token")
    room_code: str = Field(
        ..., min_length=6, max_length=6, description="6-digit room code from the facilitator quick-reg screen"
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate 11-digit Chinese mobile format"""
        v = v.strip()
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) != 11:
            raise ValueError("Phone number must be exactly 11 digits starting with 1.")
        if not v.startswith("1"):
            raise ValueError(
                "Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator("quick_reg_token")
    @classmethod
    def validate_token_strip(cls, v: str) -> str:
        """Trim surrounding whitespace from the quick-registration token."""
        return v.strip()

    @field_validator("room_code")
    @classmethod
    def validate_room_code_field(cls, v: str) -> str:
        """Ensure the room code is exactly 6 digits."""
        v = v.strip()
        if not v.isdigit():
            raise ValueError("Room code must be 6 digits, matching the code on the quick registration screen.")
        if len(v) != 6:
            raise ValueError("Room code must be exactly 6 digits.")
        return v


class QuickRegisterOpenRequest(BaseModel):
    """Request to mint a quick-registration token (managers: org from server; admins: pass organization_id)."""

    organization_id: Optional[int] = Field(
        default=None,
        description="Target organization (admins only; ignored for school managers).",
    )
    channel_type: Literal["single_use", "workshop"] = Field(
        default="single_use",
        description="single_use: one signup per token. workshop: many signups until max_uses or close.",
    )
    max_uses: Optional[int] = Field(
        default=None,
        ge=1,
        le=WORKSHOP_MAX_USES_CAP,
        description="Max registrations for workshop mode (capped server-side; default if omitted).",
    )

    @field_validator("max_uses")
    @classmethod
    def _cap_max_uses(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if v > WORKSHOP_MAX_USES_CAP:
            return WORKSHOP_MAX_USES_CAP
        return v


class QuickRegisterCloseRequest(BaseModel):
    """Request to revoke a quick-registration token."""

    token: str = Field(..., min_length=20, max_length=512, description="Opaque token to revoke")

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Trim surrounding whitespace from the token."""
        return v.strip()


class UpdateProfileNameRequest(BaseModel):
    """Self-service display name (no digits, min 2 characters)."""

    name: str = Field(..., min_length=2, max_length=100, description="Display name")

    @field_validator("name")
    @classmethod
    def validate_name_no_digits(cls, v: str) -> str:
        """Reject names shorter than two characters or containing digits."""
        t = v.strip()
        if len(t) < 2:
            raise ValueError("Name must be at least 2 characters.")
        if any(char.isdigit() for char in t):
            raise ValueError("Name cannot contain numbers.")
        return t


class SetPasswordWithSMSLoggedInRequest(BaseModel):
    """Set or replace password using SMS to the current user's phone (stays logged in; no full session revoke)."""

    new_password: StrongPassword = Field(..., min_length=8, description="New password (min 8 characters)")
    sms_code: str = Field(..., min_length=6, max_length=6, description="6-digit SMS verification code")

    @field_validator("sms_code")
    @classmethod
    def validate_sms_code(cls, v: str) -> str:
        """Ensure the SMS verification code is exactly 6 digits."""
        if not v.isdigit():
            raise ValueError("SMS verification code must be exactly 6 digits.")
        if len(v) != 6:
            raise ValueError("SMS verification code must be exactly 6 digits.")
        return v


class LoginWithSMSRequest(BaseModel):
    """Request model for login with SMS verification"""

    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    sms_code: str = Field(..., min_length=6, max_length=6, description="6-digit SMS verification code")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith("1"):
            raise ValueError(
                "Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator("sms_code")
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError(
                "SMS verification code must contain only digits. Please enter the 6-digit code sent to your phone."
            )
        if len(v) != 6:
            raise ValueError(f"SMS verification code must be exactly 6 digits. You entered {len(v)} digit(s).")
        return v

    model_config = ConfigDict(json_schema_extra={"example": {"phone": "13812345678", "sms_code": "123456"}})


class LoginWithEmailRequest(BaseModel):
    """Request model for login with email verification (SES OTP)."""

    email: str = Field(..., max_length=254, description="Account email address")
    email_code: str = Field(..., min_length=6, max_length=6, description="6-digit email verification code")

    @field_validator("email")
    @classmethod
    def strip_email(cls, v: str) -> str:
        """Trim surrounding whitespace from the email."""
        return v.strip()

    @field_validator("email_code")
    @classmethod
    def validate_email_code(cls, v: str) -> str:
        """Ensure the email verification code is exactly 6 digits."""
        v = v.strip()
        if len(v) != 6 or not v.isdigit():
            raise ValueError("Email verification code must be exactly 6 digits.")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "user@university.edu", "email_code": "123456"},
        }
    )


class ChangePasswordRequest(BaseModel):
    """Request model for /api/auth/change-password endpoint"""

    current_password: str = Field(..., min_length=4, description="Current password")
    new_password: StrongPassword = Field(..., min_length=8, description="New password (minimum 8 characters)")
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")


class ResetPasswordWithSMSRequest(BaseModel):
    """Request model for password reset with SMS verification"""

    phone: str = Field(..., min_length=11, max_length=11, description="11-digit Chinese mobile number")
    sms_code: str = Field(..., min_length=6, max_length=6, description="6-digit SMS verification code")
    new_password: StrongPassword = Field(..., min_length=8, description="New password (min 8 characters)")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith("1"):
            raise ValueError(
                "Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator("sms_code")
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError(
                "SMS verification code must contain only digits. Please enter the 6-digit code sent to your phone."
            )
        if len(v) != 6:
            raise ValueError(f"SMS verification code must be exactly 6 digits. You entered {len(v)} digit(s).")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "13812345678",
                "sms_code": "123456",
                "new_password": "NewPassword123!",
            }
        }
    )


class SendChangePhoneSMSRequest(BaseModel):
    """Request model for sending SMS code to new phone number."""

    new_phone: str = Field(
        ...,
        min_length=11,
        max_length=11,
        description="New 11-digit Chinese mobile number",
    )
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    captcha_id: str = Field(..., description="Captcha session ID")

    @field_validator("new_phone")
    @classmethod
    def validate_new_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith("1"):
            raise ValueError(
                "Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1."
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "new_phone": "13987654321",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session",
            }
        }
    )


class ChangePhoneRequest(BaseModel):
    """Request model for completing phone number change with SMS verification"""

    new_phone: str = Field(
        ...,
        min_length=11,
        max_length=11,
        description="New 11-digit Chinese mobile number",
    )
    sms_code: str = Field(..., min_length=6, max_length=6, description="6-digit SMS verification code")

    @field_validator("new_phone")
    @classmethod
    def validate_new_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(f"Phone number is too short ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if len(v) > 11:
            raise ValueError(f"Phone number is too long ({len(v)} digits). Must be exactly 11 digits starting with 1.")
        if not v.startswith("1"):
            raise ValueError(
                "Chinese mobile numbers must start with 1. Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator("sms_code")
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError(
                "SMS verification code must contain only digits. Please enter the 6-digit code sent to your phone."
            )
        if len(v) != 6:
            raise ValueError(f"SMS verification code must be exactly 6 digits. You entered {len(v)} digit(s).")
        return v

    model_config = ConfigDict(json_schema_extra={"example": {"new_phone": "13987654321", "sms_code": "123456"}})


_VALID_UI_VERSIONS = frozenset(("chinese", "international"))


class LanguagePreferencesUpdate(BaseModel):
    """PATCH body for /api/auth/language-preferences (at least one field)."""

    ui_language: Optional[str] = Field(None, max_length=32)
    prompt_language: Optional[str] = Field(None, max_length=32)
    ui_version: Optional[str] = Field(None, max_length=32)
    match_prompt_to_ui: Optional[bool] = None

    @field_validator("ui_language")
    @classmethod
    def validate_ui_language(cls, value):
        """Allow only codes in ``utils.ui_languages.UI_LANGUAGE_CODES``."""
        if value is None:
            return value
        stripped = value.strip().lower()
        if stripped not in UI_LANGUAGE_CODES:
            raise ValueError("ui_language must be a supported UI locale code")
        return stripped

    @field_validator("prompt_language")
    @classmethod
    def validate_prompt_language(cls, value):
        """Allow only registered prompt/generation language codes."""
        if value is None:
            return value
        stripped = value.strip().lower()
        if not is_prompt_output_language(stripped):
            raise ValueError("prompt_language must be a supported generation language code")
        return stripped

    @field_validator("ui_version")
    @classmethod
    def validate_ui_version(cls, value):
        """Allow ``chinese`` or ``international``."""
        if value is None:
            return value
        stripped = value.strip().lower()
        if stripped not in _VALID_UI_VERSIONS:
            raise ValueError("ui_version must be 'chinese' or 'international'")
        return stripped
