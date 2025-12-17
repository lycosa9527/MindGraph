# Error Flow Verification Checklist

## Overview
This document verifies that all SMS/Registration/Login/Captcha errors flow correctly from backend to frontend.

## Error Flow Architecture

```
Backend (routers/auth.py)
  ↓ HTTPException(status_code, detail=Messages.error(key, lang))
  ↓ Custom Handler (main.py) → {"detail": "localized message"}
  ↓ Frontend (templates/auth.html)
  ↓ extractErrorDetail() → formatAuthError() → Display
```

## Error Categories

### 1. CAPTCHA ERRORS

#### 1.1 Captcha Expired
- **Backend**: `Messages.error("captcha_expired", lang)`
- **Status**: 400
- **Message (zh)**: "验证码已过期（有效期为5分钟）。请点击刷新按钮获取新的验证码图片后重试。"
- **Message (en)**: "Captcha code has expired (valid for 5 minutes). Please click the refresh button to get a new captcha image and try again."
- **Used in**: Login, Registration, SMS Send
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 1.2 Captcha Not Found
- **Backend**: `Messages.error("captcha_not_found", lang)`
- **Status**: 400
- **Message (zh)**: "验证码会话未找到。这通常发生在页面打开时间过长时。请刷新验证码图片后重试。"
- **Used in**: Login, Registration, SMS Send
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 1.3 Captcha Incorrect
- **Backend**: `Messages.error("captcha_incorrect", lang)`
- **Status**: 400
- **Message (zh)**: "验证码不正确。请仔细检查验证码（不区分大小写）或点击刷新获取新的验证码图片后重试。"
- **Used in**: Login, Registration, SMS Send
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 1.4 Captcha Database Unavailable
- **Backend**: `Messages.error("captcha_database_unavailable", lang)`
- **Status**: 503
- **Message (zh)**: "数据库暂时繁忙，验证码验证失败。系统正在自动重试，请稍等片刻后重试。如果问题持续，请刷新页面获取新的验证码。"
- **Used in**: Login, Registration, SMS Send
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 1.5 Captcha Verify Failed
- **Backend**: `Messages.error("captcha_verify_failed", lang)`
- **Status**: 400
- **Message (zh)**: "验证码验证失败，系统暂时繁忙。请稍等片刻，刷新验证码图片后重试。如果问题持续，请尝试刷新整个页面。"
- **Used in**: Login, Registration, SMS Send
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 1.6 Captcha Retry Attempts (COMBINED)
- **Backend**: `f"{captcha_msg}{Messages.error('captcha_retry_attempts', lang, attempts_left)}"`
- **Status**: 400
- **Message (zh)**: "验证码不正确。请仔细检查验证码（不区分大小写）或点击刷新获取新的验证码图片后重试。账户锁定前还有 3 次尝试机会。"
- **Used in**: Login only
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is
- **Fix Applied**: ✅ Removed redundant "后重试" from `captcha_retry_attempts` message

#### 1.7 Captcha Account Locked
- **Backend**: `Messages.error("captcha_account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)`
- **Status**: 423
- **Message (zh)**: "账户因 10 次失败尝试而暂时锁定。请在 5 分钟后重试。"
- **Used in**: Login only
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

### 2. LOGIN ERRORS

#### 2.1 Login Failed - Phone Not Found
- **Backend**: `Messages.error("login_failed_phone_not_found", lang, attempts_left)`
- **Status**: 401
- **Message (zh)**: "登录失败。手机号未找到或密码不正确。还有 3 次尝试机会。"
- **Used in**: Login
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 2.2 Too Many Login Attempts
- **Backend**: `Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)`
- **Status**: 429
- **Message (zh)**: "登录失败次数过多。请在 15 分钟后重试。"
- **Used in**: Login
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 2.3 Invalid Password
- **Backend**: `Messages.error("invalid_password", lang, attempts_left)`
- **Status**: 401
- **Message (zh)**: "密码无效。请检查您的密码后重试。账户锁定前还有 3 次尝试机会。"
- **Used in**: Login
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 2.4 Account Locked
- **Backend**: `Messages.error("account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)`
- **Status**: 423
- **Message (zh)**: "账户因 10 次失败登录尝试而暂时锁定。请在 5 分钟后重试。"
- **Used in**: Login
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 2.5 Organization Locked
- **Backend**: `Messages.error("organization_locked", lang, org.name)`
- **Status**: 403
- **Message (zh)**: "您的学校账户（学校名）已被管理员锁定。请联系学校管理员或支持获取帮助。"
- **Used in**: Login
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 2.6 Organization Expired
- **Backend**: `Messages.error("organization_expired", lang, org.name, expired_date)`
- **Status**: 403
- **Message (zh)**: "您的学校订阅（学校名）已于 2024-01-01 过期。请联系学校管理员续订订阅。"
- **Used in**: Login
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

### 3. REGISTRATION ERRORS

#### 3.1 Registration Not Available
- **Backend**: `Messages.error("registration_not_available", lang, AUTH_MODE)`
- **Status**: 403
- **Message (zh)**: "demo 模式下注册不可用。请改用密钥认证。"
- **Used in**: Registration, SMS Send (register purpose)
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 3.2 Phone Already Registered
- **Backend**: `Messages.error("phone_already_registered", lang)`
- **Status**: 409
- **Message (zh)**: "该手机号已注册。请直接登录或使用其他手机号。"
- **Used in**: Registration, SMS Send (register purpose)
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 3.3 Invitation Code Required
- **Backend**: `Messages.error("invitation_code_required", lang)`
- **Status**: 400
- **Message (zh)**: "需要邀请码。请输入学校管理员提供的邀请码。"
- **Used in**: Registration, Register SMS
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 3.4 Invitation Code Invalid Format
- **Backend**: `Messages.error("invitation_code_invalid_format", lang, request.invitation_code)`
- **Status**: 400
- **Message (zh)**: "邀请码格式无效。期望格式：AAAA-XXXXX（4个字母，短横线，5个字母数字字符）。您输入的是：INVALID"
- **Used in**: Registration, Register SMS
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 3.5 Invitation Code Not Found
- **Backend**: `Messages.error("invitation_code_not_found", lang, request.invitation_code)`
- **Status**: 403
- **Message (zh)**: "邀请码 'INVALID' 无效或不存在。请检查学校管理员提供的邀请码，或如果您认为这是错误，请联系支持。"
- **Used in**: Registration, Register SMS
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

### 4. SMS ERRORS

#### 4.1 SMS Service Not Configured
- **Backend**: `Messages.error("sms_service_not_configured", lang)`
- **Status**: 503
- **Message (zh)**: "短信服务未配置。请联系支持或使用基于密码的认证。"
- **Used in**: SMS Send
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 4.2 Phone Not Registered (Login)
- **Backend**: `Messages.error("phone_not_registered_login", lang)`
- **Status**: 404
- **Message (zh)**: "该手机号未注册。请检查您的手机号或注册新账户。"
- **Used in**: SMS Send (login purpose)
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 4.3 Phone Not Registered (Reset)
- **Backend**: `Messages.error("phone_not_registered_reset", lang)`
- **Status**: 404
- **Message (zh)**: "该手机号未注册。请检查您的手机号或联系支持。"
- **Used in**: SMS Send (reset_password purpose)
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 4.4 SMS Cooldown (Minutes)
- **Backend**: `Messages.error("sms_cooldown_minutes", lang, wait_minutes)`
- **Status**: 429
- **Message (zh)**: "请等待 2 分钟后再请求新的短信验证码。该号码最近已收到验证码。"
- **Used in**: SMS Send
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 4.5 SMS Cooldown (Seconds)
- **Backend**: `Messages.error("sms_cooldown_seconds", lang, wait_seconds)`
- **Status**: 429
- **Message (zh)**: "请等待 30 秒后再请求新的短信验证码。该号码最近已收到验证码。"
- **Used in**: SMS Send
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 4.6 Too Many SMS Requests
- **Backend**: `Messages.error("too_many_sms_requests", lang, window_count, SMS_MAX_ATTEMPTS_WINDOW_HOURS)`
- **Status**: 429
- **Message (zh)**: "短信验证码请求过多（5 次请求在 1 小时内）。请稍后再试。"
- **Used in**: SMS Send
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 4.7 SMS Code Expired
- **Backend**: `Messages.error("sms_code_expired", lang, SMS_CODE_EXPIRY_MINUTES)`
- **Status**: 400
- **Message (zh)**: "短信验证码已过期。验证码有效期为 10 分钟。请申请新的验证码。"
- **Used in**: SMS Verify, Register SMS, Login SMS, Reset Password
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 4.8 SMS Code Invalid
- **Backend**: `Messages.error("sms_code_invalid", lang)`
- **Status**: 400
- **Message (zh)**: "短信验证码无效。请检查验证码后重试，或申请新的验证码。"
- **Used in**: SMS Verify, Register SMS, Login SMS, Reset Password
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 4.9 SMS Code Already Used
- **Backend**: `Messages.error("sms_code_already_used", lang)`
- **Status**: 400
- **Message (zh)**: "该短信验证码已被使用。每个验证码只能使用一次。请申请新的验证码。"
- **Used in**: Register SMS, Login SMS, Reset Password
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

#### 4.10 SMS Service Temporarily Unavailable
- **Backend**: `Messages.error("sms_service_temporarily_unavailable", lang)`
- **Status**: 500
- **Message (zh)**: "短信服务暂时不可用。请稍后重试，如果问题持续存在，请联系支持。"
- **Used in**: SMS Send
- **Frontend handling**: ✅ Detected by Chinese character pattern, displayed as-is

## Issues Found and Fixed

### Issue 1: Redundant Text in Combined Captcha Messages ✅ FIXED
**Location**: `models/messages.py` line 122-126
**Problem**: When combining captcha error with retry attempts, "后重试" appeared twice:
- `captcha_incorrect` ends with: "...后重试。"
- `captcha_retry_attempts` started with: "后重试。账户锁定前还有 {} 次尝试机会。"

**Fix Applied**: Removed "后重试" from `captcha_retry_attempts` message in all languages:
- **Before (zh)**: "后重试。账户锁定前还有 {} 次尝试机会。"
- **After (zh)**: "账户锁定前还有 {} 次尝试机会。"
- **Before (en)**: " and try again. {} attempt(s) remaining before account lockout."
- **After (en)**: " {} attempt(s) remaining before account lockout."

**Result**: Clean combined message: "验证码不正确。请仔细检查验证码（不区分大小写）或点击刷新获取新的验证码图片后重试。账户锁定前还有 3 次尝试机会。"

## Verification Status

### ✅ All Error Types Verified
- All error messages use `Messages.error()` with proper localization
- All errors return `{"detail": "localized message"}` format
- Frontend correctly detects Chinese characters and displays as-is
- Frontend handles both `result.detail` and `result.error` for compatibility

### ✅ All Issues Fixed
1. ✅ Redundant "后重试" in combined captcha messages - FIXED
2. ✅ Hardcoded English messages in `check_rate_limit()` - FIXED (now uses Messages.error)
3. ✅ Hardcoded English messages in `check_account_lockout()` - FIXED (now uses Messages.error)

## Testing Recommendations

1. **Test each error type** with Chinese language header
2. **Test each error type** with English language header  
3. **Test combined messages** (captcha + attempts) for redundancy
4. **Test edge cases**: Empty detail, non-string detail, missing fields
5. **Test Pydantic 422 errors** (array format) separately

