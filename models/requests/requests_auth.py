"""Authentication and SMS Verification Request Models.

Pydantic models for validating authentication and SMS verification API requests.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# AUTHENTICATION REQUEST MODELS
# ============================================================================

class RegisterRequest(BaseModel):
    """Request model for user registration"""
    phone: str = Field(
        ..., min_length=11, max_length=11,
        description="11-digit Chinese mobile number"
    )
    password: str = Field(
        ..., min_length=8, description="Password (min 8 characters)"
    )
    name: str = Field(
        ..., min_length=2,
        description="Teacher's name (required, min 2 chars, no numbers)"
    )
    invitation_code: str = Field(
        ...,
        description=(
            "Invitation code for registration "
            "(automatically binds to school)"
        )
    )
    captcha: str = Field(
        ..., min_length=4, max_length=4,
        description="4-character captcha code"
    )
    captcha_id: str = Field(..., description="Captcha session ID")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. "
                "Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(
                f"Phone number is too short ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if len(v) > 11:
            raise ValueError(
                f"Phone number is too long ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if not v.startswith('1'):
            raise ValueError(
                "Chinese mobile numbers must start with 1. "
                "Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate name has no numbers"""
        if len(v) < 2:
            raise ValueError(
                f"Name is too short ({len(v)} character(s)). "
                "Must be at least 2 characters."
            )
        if any(char.isdigit() for char in v):
            raise ValueError(
                "Name cannot contain numbers. "
                "Please enter your name using letters only."
            )
        return v

    class Config:
        """Configuration for RegisterRequest model."""

        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "password": "Teacher123!",
                "name": "Zhang Wei",
                "invitation_code": "DEMO-A1B2C",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session"
            }
        }


class LoginRequest(BaseModel):
    """Request model for user login"""
    phone: str = Field(..., description="User phone number")
    password: str = Field(..., description="User password")
    captcha: str = Field(
        ..., min_length=4, max_length=4,
        description="4-character captcha code"
    )
    captcha_id: str = Field(..., description="Captcha session ID")

    class Config:
        """Configuration for LoginRequest model."""

        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "password": "Teacher123!",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session"
            }
        }


class DemoPasskeyRequest(BaseModel):
    """Request model for demo mode passkey verification"""
    passkey: str = Field(
        ..., min_length=6, max_length=6,
        description="6-digit demo passkey"
    )

    @field_validator('passkey')
    @classmethod
    def validate_passkey(cls, v):
        """Validate 6-digit passkey"""
        if not v.isdigit():
            raise ValueError("Passkey must contain only digits")
        if len(v) != 6:
            raise ValueError("Passkey must be exactly 6 digits")
        return v

    class Config:
        """Configuration for DemoPasskeyRequest model."""

        json_schema_extra = {
            "example": {
                "passkey": "888888"
            }
        }


# ============================================================================
# SMS VERIFICATION REQUEST MODELS
# ============================================================================

class SendSMSCodeRequest(BaseModel):
    """Request model for sending SMS verification code"""
    phone: str = Field(
        ..., min_length=11, max_length=11,
        description="11-digit Chinese mobile number"
    )
    purpose: str = Field(
        ...,
        description="Purpose: 'register', 'login', or 'reset_password'"
    )
    captcha: str = Field(
        ..., min_length=4, max_length=4,
        description="4-character captcha code"
    )
    captcha_id: str = Field(..., description="Captcha session ID")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. "
                "Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(
                f"Phone number is too short ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if len(v) > 11:
            raise ValueError(
                f"Phone number is too long ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if not v.startswith('1'):
            raise ValueError(
                "Chinese mobile numbers must start with 1. "
                "Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator('purpose')
    @classmethod
    def validate_purpose(cls, v):
        """Validate SMS purpose"""
        valid_purposes = [
            'register', 'login', 'reset_password', 'change_phone'
        ]
        if v not in valid_purposes:
            raise ValueError(
                f"Purpose must be one of: {', '.join(valid_purposes)}"
            )
        return v

    class Config:
        """Configuration for SendSMSCodeRequest model."""

        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "purpose": "register",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session"
            }
        }


class SendSMSCodeSimpleRequest(BaseModel):
    """Simplified request model for purpose-specific SMS endpoints."""
    phone: str = Field(
        ..., min_length=11, max_length=11,
        description="11-digit Chinese mobile number"
    )
    captcha: str = Field(
        ..., min_length=4, max_length=4,
        description="4-character captcha code"
    )
    captcha_id: str = Field(..., description="Captcha session ID")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. "
                "Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(
                f"Phone number is too short ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if len(v) > 11:
            raise ValueError(
                f"Phone number is too long ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if not v.startswith('1'):
            raise ValueError(
                "Chinese mobile numbers must start with 1. "
                "Please enter a valid 11-digit number starting with 1."
            )
        return v

    class Config:
        """Configuration for SendSMSCodeSimpleRequest model."""

        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session"
            }
        }


class VerifySMSCodeRequest(BaseModel):
    """Request model for verifying SMS code (standalone verification)"""
    phone: str = Field(
        ..., min_length=11, max_length=11,
        description="11-digit Chinese mobile number"
    )
    code: str = Field(
        ..., min_length=6, max_length=6,
        description="6-digit SMS verification code"
    )
    purpose: str = Field(
        ..., description="Purpose: 'register', 'login', or 'reset_password'"
    )

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. "
                "Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(
                f"Phone number is too short ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if len(v) > 11:
            raise ValueError(
                f"Phone number is too long ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if not v.startswith('1'):
            raise ValueError(
                "Chinese mobile numbers must start with 1. "
                "Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator('code')
    @classmethod
    def validate_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError(
                "SMS verification code must contain only digits. "
                "Please enter the 6-digit code sent to your phone."
            )
        if len(v) != 6:
            raise ValueError(
                f"SMS verification code must be exactly 6 digits. "
                f"You entered {len(v)} digit(s)."
            )
        return v

    class Config:
        """Configuration for VerifySMSCodeRequest model."""

        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "code": "123456",
                "purpose": "register"
            }
        }


class RegisterWithSMSRequest(BaseModel):
    """Request model for registration with SMS verification"""
    phone: str = Field(
        ..., min_length=11, max_length=11,
        description="11-digit Chinese mobile number"
    )
    password: str = Field(
        ..., min_length=8, description="Password (min 8 characters)"
    )
    name: str = Field(
        ..., min_length=2,
        description="Teacher's name (required, min 2 chars, no numbers)"
    )
    invitation_code: str = Field(
        ..., description="Invitation code for registration"
    )
    sms_code: str = Field(
        ..., min_length=6, max_length=6,
        description="6-digit SMS verification code"
    )

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. "
                "Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(
                f"Phone number is too short ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if len(v) > 11:
            raise ValueError(
                f"Phone number is too long ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if not v.startswith('1'):
            raise ValueError(
                "Chinese mobile numbers must start with 1. "
                "Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate name has no numbers"""
        if len(v) < 2:
            raise ValueError(
                f"Name is too short ({len(v)} character(s)). "
                "Must be at least 2 characters."
            )
        if any(char.isdigit() for char in v):
            raise ValueError(
                "Name cannot contain numbers. "
                "Please enter your name using letters only."
            )
        return v

    @field_validator('sms_code')
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError(
                "SMS verification code must contain only digits. "
                "Please enter the 6-digit code sent to your phone."
            )
        if len(v) != 6:
            raise ValueError(
                f"SMS verification code must be exactly 6 digits. "
                f"You entered {len(v)} digit(s)."
            )
        return v

    class Config:
        """Configuration for RegisterWithSMSRequest model."""

        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "password": "Teacher123!",
                "name": "Zhang Wei",
                "invitation_code": "DEMO-A1B2C",
                "sms_code": "123456"
            }
        }


class LoginWithSMSRequest(BaseModel):
    """Request model for login with SMS verification"""
    phone: str = Field(
        ..., min_length=11, max_length=11,
        description="11-digit Chinese mobile number"
    )
    sms_code: str = Field(
        ..., min_length=6, max_length=6,
        description="6-digit SMS verification code"
    )

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. "
                "Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(
                f"Phone number is too short ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if len(v) > 11:
            raise ValueError(
                f"Phone number is too long ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if not v.startswith('1'):
            raise ValueError(
                "Chinese mobile numbers must start with 1. "
                "Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator('sms_code')
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError(
                "SMS verification code must contain only digits. "
                "Please enter the 6-digit code sent to your phone."
            )
        if len(v) != 6:
            raise ValueError(
                f"SMS verification code must be exactly 6 digits. "
                f"You entered {len(v)} digit(s)."
            )
        return v

    class Config:
        """Configuration for LoginWithSMSRequest model."""

        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "sms_code": "123456"
            }
        }


class ChangePasswordRequest(BaseModel):
    """Request model for /api/auth/change-password endpoint"""
    current_password: str = Field(
        ..., min_length=4, description="Current password"
    )
    new_password: str = Field(
        ..., min_length=8,
        description="New password (minimum 8 characters)"
    )


class ResetPasswordWithSMSRequest(BaseModel):
    """Request model for password reset with SMS verification"""
    phone: str = Field(
        ..., min_length=11, max_length=11,
        description="11-digit Chinese mobile number"
    )
    sms_code: str = Field(
        ..., min_length=6, max_length=6,
        description="6-digit SMS verification code"
    )
    new_password: str = Field(
        ..., min_length=8, description="New password (min 8 characters)"
    )

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. "
                "Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(
                f"Phone number is too short ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if len(v) > 11:
            raise ValueError(
                f"Phone number is too long ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if not v.startswith('1'):
            raise ValueError(
                "Chinese mobile numbers must start with 1. "
                "Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator('sms_code')
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError(
                "SMS verification code must contain only digits. "
                "Please enter the 6-digit code sent to your phone."
            )
        if len(v) != 6:
            raise ValueError(
                f"SMS verification code must be exactly 6 digits. "
                f"You entered {len(v)} digit(s)."
            )
        return v

    class Config:
        """Configuration for ResetPasswordWithSMSRequest model."""

        json_schema_extra = {
            "example": {
                "phone": "13812345678",
                "sms_code": "123456",
                "new_password": "NewPassword123!"
            }
        }


class SendChangePhoneSMSRequest(BaseModel):
    """Request model for sending SMS code to new phone number."""
    new_phone: str = Field(
        ..., min_length=11, max_length=11,
        description="New 11-digit Chinese mobile number"
    )
    captcha: str = Field(
        ..., min_length=4, max_length=4,
        description="4-character captcha code"
    )
    captcha_id: str = Field(..., description="Captcha session ID")

    @field_validator('new_phone')
    @classmethod
    def validate_new_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. "
                "Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(
                f"Phone number is too short ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if len(v) > 11:
            raise ValueError(
                f"Phone number is too long ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if not v.startswith('1'):
            raise ValueError(
                "Chinese mobile numbers must start with 1. "
                "Please enter a valid 11-digit number starting with 1."
            )
        return v

    class Config:
        """Configuration for SendChangePhoneSMSRequest model."""

        json_schema_extra = {
            "example": {
                "new_phone": "13987654321",
                "captcha": "AB3D",
                "captcha_id": "uuid-captcha-session"
            }
        }


class ChangePhoneRequest(BaseModel):
    """Request model for completing phone number change with SMS verification"""
    new_phone: str = Field(
        ..., min_length=11, max_length=11,
        description="New 11-digit Chinese mobile number"
    )
    sms_code: str = Field(
        ..., min_length=6, max_length=6,
        description="6-digit SMS verification code"
    )

    @field_validator('new_phone')
    @classmethod
    def validate_new_phone(cls, v):
        """Validate 11-digit Chinese mobile format"""
        if not v.isdigit():
            raise ValueError(
                "Phone number must contain only digits. "
                "Please enter a valid 11-digit Chinese mobile number."
            )
        if len(v) < 11:
            raise ValueError(
                f"Phone number is too short ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if len(v) > 11:
            raise ValueError(
                f"Phone number is too long ({len(v)} digits). "
                "Must be exactly 11 digits starting with 1."
            )
        if not v.startswith('1'):
            raise ValueError(
                "Chinese mobile numbers must start with 1. "
                "Please enter a valid 11-digit number starting with 1."
            )
        return v

    @field_validator('sms_code')
    @classmethod
    def validate_sms_code(cls, v):
        """Validate 6-digit SMS code"""
        if not v.isdigit():
            raise ValueError(
                "SMS verification code must contain only digits. "
                "Please enter the 6-digit code sent to your phone."
            )
        if len(v) != 6:
            raise ValueError(
                f"SMS verification code must be exactly 6 digits. "
                f"You entered {len(v)} digit(s)."
            )
        return v

    class Config:
        """Configuration for ChangePhoneRequest model."""

        json_schema_extra = {
            "example": {
                "new_phone": "13987654321",
                "sms_code": "123456"
            }
        }
