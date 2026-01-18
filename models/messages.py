"""Centralized Bilingual Message System for MindGraph.

Provides all user-facing messages (errors, success, warnings) in both Chinese
and English. Used by API endpoints to return localized error messages.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司
(Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Literal, Optional


Language = Literal["zh", "en", "az"]


class Messages:
    """Centralized bilingual message system"""

    # API Error Messages
    ERRORS = {
        "message_required": {
            "zh": "消息不能为空",
            "en": "Message is required",
            "az": "Mesaj tələb olunur"
        },
        "ai_not_configured": {
            "zh": "AI助手未配置",
            "en": "AI assistant not configured",
            "az": "AI köməkçisi konfiqurasiya edilməyib"
        },
        "invalid_prompt": {
            "zh": "提示词无效或为空",
            "en": "Invalid or empty prompt",
            "az": "Etibarsız və ya boş prompt"
        },
        "diagram_data_required": {
            "zh": "需要图示数据",
            "en": "Diagram data is required",
            "az": "Diaqram məlumatı tələb olunur"
        },
        "generation_failed": {
            "zh": "生成图示失败：{}",
            "en": "Failed to generate graph: {}",
            "az": "Qrafik yaratmaq mümkün olmadı: {}"
        },
        "export_failed": {
            "zh": "导出PNG失败：{}",
            "en": "PNG export failed: {}",
            "az": "PNG ixracı uğursuz oldu: {}"
        },
        "internal_error": {
            "zh": "服务器内部错误",
            "en": "Internal server error",
            "az": "Daxili server xətası"
        },
        "invalid_request": {
            "zh": "请求无效",
            "en": "Invalid request",
            "az": "Etibarsız sorğu"
        },
        "captcha_generate_failed": {
            "zh": (
                "验证码生成失败，系统暂时繁忙。请等待几秒后刷新页面重试。"
                "如果问题持续，系统可能正在处理高负载请求。"
            ),
            "en": (
                "Failed to generate captcha due to a temporary system issue. "
                "Please wait a few seconds and refresh the page to try again. "
                "If the problem persists, the system may be experiencing high load."
            ),
            "az": (
                "Captcha yaratmaq mümkün olmadı, sistem müvəqqəti məşğuldur. "
                "Bir neçə saniyə gözləyin və səhifəni yeniləyin. "
                "Problem davam edərsə, sistem yüksək yüklə işləyir."
            )
        },
        "captcha_expired": {
            "zh": (
                "验证码已过期（有效期为5分钟）。"
                "请点击刷新按钮获取新的验证码图片后重试。"
            ),
            "en": (
                "Captcha code has expired (valid for 5 minutes). "
                "Please click the refresh button to get a new captcha image "
                "and try again."
            ),
            "az": (
                "Captcha kodu müddəti bitib (5 dəqiqə etibarlıdır). "
                "Yeniləmə düyməsini klikləyin və yeni captcha şəkli alın."
            )
        },
        "captcha_not_found": {
            "zh": (
                "验证码会话未找到。这通常发生在页面打开时间过长时。"
                "请刷新验证码图片后重试。"
            ),
            "en": (
                "Captcha session not found. This usually happens if the page "
                "was open for too long. Please refresh the captcha image and "
                "try again."
            ),
            "az": (
                "Captcha sessiyası tapılmadı. Bu adətən səhifə çox uzun "
                "müddət açıq qaldıqda baş verir. Captcha şəklini yeniləyin."
            )
        },
        "captcha_incorrect": {
            "zh": (
                "验证码不正确。请仔细检查验证码（不区分大小写）"
                "或点击刷新获取新的验证码图片后重试。"
            ),
            "en": (
                "Captcha code is incorrect. Please double-check the code "
                "(case-insensitive) or click refresh to get a new captcha "
                "image and try again."
            ),
            "az": (
                "Captcha kodu yanlışdır. Kodu yenidən yoxlayın "
                "(böyük/kiçik hərf fərqi yoxdur) və ya yeniləyin."
            )
        },
        "captcha_verify_failed": {
            "zh": (
                "验证码验证失败，系统暂时繁忙。请稍等片刻，刷新验证码图片后重试。"
                "如果问题持续，请尝试刷新整个页面。"
            ),
            "en": (
                "Captcha verification failed due to a temporary system issue. "
                "Please wait a moment, refresh the captcha image, and try again. "
                "If the problem persists, try refreshing the entire page."
            ),
            "az": (
                "Captcha yoxlanışı müvəqqəti sistem problemi səbəbindən "
                "uğursuz oldu. Bir az gözləyin, captcha şəklini yeniləyin "
                "və yenidən cəhd edin."
            )
        },
        "captcha_database_unavailable": {
            "zh": (
                "数据库暂时繁忙，验证码验证失败。系统正在自动重试，"
                "请稍等片刻后重试。如果问题持续，请刷新页面获取新的验证码。"
            ),
            "en": (
                "Database is temporarily busy, captcha verification failed. "
                "The system is automatically retrying. Please wait a moment and "
                "try again. If the problem persists, please refresh the page "
                "to get a new captcha."
            ),
            "az": (
                "Verilənlər bazası müvəqqəti olaraq məşğuldur, "
                "captcha yoxlanışı uğursuz oldu. Sistem avtomatik olaraq "
                "yenidən cəhd edir. Bir az gözləyin və yenidən cəhd edin."
            )
        },
        "database_temporarily_unavailable": {
            "zh": "数据库暂时繁忙，请稍后重试。",
            "en": "Database is temporarily unavailable. Please try again later.",
            "az": "Verilənlər bazası müvəqqəti olaraq mövcud deyil. Daha sonra yenidən cəhd edin."
        },
        "captcha_retry_attempts": {
            "zh": "账户锁定前还有 {} 次尝试机会。",
            "en": " {} attempt(s) remaining before account lockout.",
            "az": "Hesab kilidlənməsindən əvvəl {} cəhd qalıb."
        },
        "captcha_account_locked": {
            "zh": "账户因 {} 次失败尝试而暂时锁定。请在 {} 分钟后重试。",
            "en": "Account temporarily locked due to {} failed attempts. Please try again in {} minutes.",
            "az": "Hesab {} uğursuz cəhd səbəbindən müvəqqəti olaraq kilidlənib. {} dəqiqədən sonra yenidən cəhd edin."
        },
        "phone_already_registered": {
            "zh": "该手机号已注册。请直接登录或使用其他手机号。",
            "en": "This phone number is already registered. Please use login instead or try a different phone number.",
            "az": "Bu telefon nömrəsi artıq qeydiyyatdan keçib. Giriş edin və ya başqa telefon nömrəsi istifadə edin."
        },
        "invitation_code_required": {
            "zh": "需要邀请码。请输入学校管理员提供的邀请码。",
            "en": (
                "Invitation code is required. Please enter the invitation code "
                "provided by your school administrator."
            ),
            "az": (
                "Dəvət kodu tələb olunur. Məktəb administratoru tərəfindən "
                "təmin edilən dəvət kodunu daxil edin."
            )
        },
        "invitation_code_invalid_format": {
            "zh": (
                "邀请码格式无效。期望格式：AAAA-XXXXX"
                "（4个字母，短横线，5个字母数字字符）。您输入的是：{}"
            ),
            "en": (
                "Invalid invitation code format. Expected format: AAAA-XXXXX "
                "(4 letters, dash, 5 alphanumeric characters). "
                "You entered: {}"
            ),
            "az": (
                "Etibarsız dəvət kodu formatı. Gözlənilən format: AAAA-XXXXX "
                "(4 hərf, tire, 5 hərf-rəqəm simvolu). Siz daxil etdiniz: {}"
            )
        },
        "invitation_code_not_found": {
            "zh": (
                "邀请码 '{}' 无效或不存在。请检查学校管理员提供的邀请码，"
                "或如果您认为这是错误，请联系支持。"
            ),
            "en": (
                "Invitation code '{}' is not valid or does not exist. "
                "Please check the code provided by your school administrator, "
                "or contact support if you believe this is an error."
            ),
            "az": (
                "Dəvət kodu '{}' etibarsızdır və ya mövcud deyil. "
                "Məktəb administratoru tərəfindən təmin edilən kodu yoxlayın "
                "və ya səhv olduğunu düşünürsünüzsə, dəstəklə əlaqə saxlayın."
            )
        },
        "registration_not_available": {
            "zh": "{} 模式下注册不可用。请改用密钥认证。",
            "en": "Registration is not available in {} mode. Please use passkey authentication instead.",
            "az": "{} rejimində qeydiyyat mövcud deyil. Bunun əvəzinə passkey autentifikasiyasından istifadə edin."
        },
        "login_failed_phone_not_found": {
            "zh": (
                "登录失败。手机号未找到或密码不正确。还有 {} 次尝试机会。"
            ),
            "en": (
                "Login failed. Phone number not found or password incorrect. "
                "{} attempt(s) remaining."
            ),
            "az": (
                "Giriş uğursuz oldu. Telefon nömrəsi tapılmadı "
                "və ya parol yanlışdır. {} cəhd qalıb."
            )
        },
        "too_many_login_attempts": {
            "zh": "登录失败次数过多。请在 {} 分钟后重试。",
            "en": "Too many failed login attempts. Please try again in {} minutes.",
            "az": "Çox sayda uğursuz giriş cəhdi. {} dəqiqədən sonra yenidən cəhd edin."
        },
        "invalid_password": {
            "zh": (
                "密码无效。请检查您的密码后重试。"
                "账户锁定前还有 {} 次尝试机会。"
            ),
            "en": (
                "Invalid password. Please check your password and try again. "
                "{} attempt(s) remaining before account lockout."
            ),
            "az": (
                "Etibarsız parol. Parolunuzu yoxlayın və yenidən cəhd edin. "
                "Hesab kilidlənməsindən əvvəl {} cəhd qalıb."
            )
        },
        "account_locked": {
            "zh": (
                "账户因 {} 次失败登录尝试而暂时锁定。请在 {} 分钟后重试。"
            ),
            "en": (
                "Account temporarily locked due to {} failed login attempts. "
                "Please try again in {} minutes."
            ),
            "az": (
                "Hesab {} uğursuz giriş cəhdi səbəbindən müvəqqəti olaraq "
                "kilidlənib. {} dəqiqədən sonra yenidən cəhd edin."
            )
        },
        "organization_locked": {
            "zh": (
                "您的学校账户（{}）已被管理员锁定。"
                "请联系学校管理员或支持获取帮助。"
            ),
            "en": (
                "Your school account ({}) has been locked by the administrator. "
                "Please contact your school administrator or support for "
                "assistance."
            ),
            "az": (
                "Məktəb hesabınız ({}) administrator tərəfindən kilidlənib. "
                "Yardım üçün məktəb administratoru və ya dəstəklə əlaqə saxlayın."
            )
        },
        "organization_expired": {
            "zh": (
                "您的学校订阅（{}）已于 {} 过期。"
                "请联系学校管理员续订订阅。"
            ),
            "en": (
                "Your school subscription ({}) expired on {}. "
                "Please contact your school administrator to renew the "
                "subscription."
            ),
            "az": (
                "Məktəb abunəliyiniz ({}) {} tarixində bitib. "
                "Abunəliyi yeniləmək üçün məktəb administratoru ilə "
                "əlaqə saxlayın."
            )
        },
        "sms_service_not_configured": {
            "zh": "短信服务未配置。请联系支持或使用基于密码的认证。",
            "en": (
                "SMS service is not configured. Please contact support or "
                "use password-based authentication instead."
            ),
            "az": (
                "SMS xidməti konfiqurasiya edilməyib. Dəstəklə əlaqə saxlayın "
                "və ya bunun əvəzinə parol əsaslı autentifikasiyadan istifadə edin."
            )
        },
        "phone_not_registered_login": {
            "zh": "该手机号未注册。请检查您的手机号或注册新账户。",
            "en": (
                "This phone number is not registered. Please check your "
                "phone number or register a new account."
            ),
            "az": (
                "Bu telefon nömrəsi qeydiyyatdan keçməyib. "
                "Telefon nömrənizi yoxlayın və ya yeni hesab qeydiyyatdan keçirin."
            )
        },
        "phone_not_registered_reset": {
            "zh": "该手机号未注册。请检查您的手机号或联系支持。",
            "en": (
                "This phone number is not registered. Please check your "
                "phone number or contact support."
            ),
            "az": (
                "Bu telefon nömrəsi qeydiyyatdan keçməyib. "
                "Telefon nömrənizi yoxlayın və ya dəstəklə əlaqə saxlayın."
            )
        },
        "sms_cooldown_minutes": {
            "zh": (
                "请等待 {} 分钟后再请求新的短信验证码。该号码最近已收到验证码。"
            ),
            "en": (
                "Please wait {} minute(s) before requesting a new SMS code. "
                "A code was recently sent to this number."
            ),
            "az": (
                "Yeni SMS kodu tələb etməzdən əvvəl {} dəqiqə gözləyin. "
                "Bu nömrəyə yaxınlarda kod göndərilib."
            )
        },
        "sms_cooldown_seconds": {
            "zh": (
                "请等待 {} 秒后再请求新的短信验证码。该号码最近已收到验证码。"
            ),
            "en": (
                "Please wait {} second(s) before requesting a new SMS code. "
                "A code was recently sent to this number."
            ),
            "az": (
                "Yeni SMS kodu tələb etməzdən əvvəl {} saniyə gözləyin. "
                "Bu nömrəyə yaxınlarda kod göndərilib."
            )
        },
        "too_many_sms_requests": {
            "zh": (
                "短信验证码请求过多（{} 次请求在 {} 小时内）。请稍后再试。"
            ),
            "en": (
                "Too many SMS verification code requests "
                "({} requests in {} hour(s)). Please try again later."
            ),
            "az": (
                "Çox sayda SMS təsdiq kodu sorğusu ({} sorğu {} saat ərzində). "
                "Daha sonra yenidən cəhd edin."
            )
        },
        "sms_code_expired": {
            "zh": (
                "短信验证码已过期。验证码有效期为 {} 分钟。请申请新的验证码。"
            ),
            "en": (
                "SMS verification code has expired. Codes are valid for {} "
                "minutes. Please request a new code."
            ),
            "az": (
                "SMS təsdiq kodu müddəti bitib. Kodlar {} dəqiqə etibarlıdır. "
                "Yeni kod tələb edin."
            )
        },
        "sms_code_invalid": {
            "zh": "短信验证码无效。请检查验证码后重试，或申请新的验证码。",
            "en": (
                "Invalid SMS verification code. Please check the code and "
                "try again, or request a new code."
            ),
            "az": (
                "Etibarsız SMS təsdiq kodu. Kodu yoxlayın və yenidən cəhd edin "
                "və ya yeni kod tələb edin."
            )
        },
        "sms_code_already_used": {
            "zh": (
                "该短信验证码已被使用。每个验证码只能使用一次。请申请新的验证码。"
            ),
            "en": (
                "This SMS verification code has already been used. "
                "Each code can only be used once. Please request a new code."
            ),
            "az": (
                "Bu SMS təsdiq kodu artıq istifadə olunub. "
                "Hər kod yalnız bir dəfə istifadə edilə bilər. Yeni kod tələb edin."
            )
        },
        "sms_service_temporarily_unavailable": {
            "zh": (
                "短信服务暂时不可用。请稍后重试，如果问题持续存在，请联系支持。"
            ),
            "en": (
                "SMS service is temporarily unavailable. Please try again later "
                "or contact support if the problem persists."
            ),
            "az": (
                "SMS xidməti müvəqqəti olaraq mövcud deyil. "
                "Daha sonra yenidən cəhd edin və ya problem davam edərsə "
                "dəstəklə əlaqə saxlayın."
            )
        },
        # SMS Error Codes - FailedOperation
        "sms_error_contain_sensitive_word": {
            "zh": "短信内容包含敏感词。请联系技术支持获取帮助。",
            "en": "SMS content contains sensitive words. Please contact support for assistance.",
            "az": "SMS məzmunu həssas sözlər ehtiva edir. Yardım üçün dəstəklə əlaqə saxlayın."
        },
        "sms_error_fail_resolve_packet": {
            "zh": "短信请求解析失败。请稍后重试或联系技术支持。",
            "en": "SMS request parsing failed. Please try again later or contact support.",
            "az": "SMS sorğusu analizi uğursuz oldu. Daha sonra yenidən cəhd edin və ya dəstəklə əlaqə saxlayın."
        },
        "sms_error_insufficient_balance": {
            "zh": "短信服务余额不足。请联系技术支持。",
            "en": "SMS service balance insufficient. Please contact support.",
            "az": "SMS xidməti balansı kifayət etmir. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_marketing_time_constraint": {
            "zh": "营销短信只能在8:00-22:00之间发送。请在营业时间内重试。",
            "en": "Marketing SMS can only be sent between 8:00-22:00. Please try again during business hours.",
            "az": "Marketinq SMS-i yalnız 8:00-22:00 arasında göndərilə bilər. İş saatları ərzində yenidən cəhd edin."
        },
        "sms_error_phone_in_blacklist": {
            "zh": "该手机号已被禁止接收短信。请联系技术支持获取帮助。",
            "en": "This phone number is blocked from receiving SMS. Please contact support for assistance.",
            "az": "Bu telefon nömrəsi SMS qəbul etməkdən qadağandır. Yardım üçün dəstəklə əlaqə saxlayın."
        },
        "sms_error_signature_config": {
            "zh": "短信签名配置错误。请联系技术支持。",
            "en": "SMS signature configuration error. Please contact support.",
            "az": "SMS imza konfiqurasiyası xətası. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_template_config": {
            "zh": "短信模板配置错误。请联系技术支持。",
            "en": "SMS template configuration error. Please contact support.",
            "az": "SMS şablon konfiqurasiyası xətası. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_template_params_mismatch": {
            "zh": "短信模板参数不匹配。请联系技术支持。",
            "en": "SMS template parameters do not match. Please contact support.",
            "az": "SMS şablon parametrləri uyğun gəlmir. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_template_unapproved": {
            "zh": "短信模板未审批或不存在。请联系技术支持。",
            "en": "SMS template not approved or does not exist. Please contact support.",
            "az": "SMS şablonu təsdiq edilməyib və ya mövcud deyil. Dəstəklə əlaqə saxlayın."
        },
        # SMS Error Codes - InternalError
        "sms_error_internal_other": {
            "zh": "短信服务遇到错误。请稍后重试或联系技术支持。",
            "en": "SMS service encountered an error. Please try again later or contact support.",
            "az": "SMS xidməti xəta ilə üzləşdi. Daha sonra yenidən cəhd edin və ya dəstəklə əlaqə saxlayın."
        },
        "sms_error_request_time": {
            "zh": "短信请求时间错误。请检查系统时间后重试。",
            "en": "SMS request time error. Please check system time and try again.",
            "az": "SMS sorğu vaxtı xətası. Sistem vaxtını yoxlayın və yenidən cəhd edin."
        },
        "sms_error_api_interface": {
            "zh": "短信API接口错误。请联系技术支持。",
            "en": "SMS API interface error. Please contact support.",
            "az": "SMS API interfeysi xətası. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_timeout": {
            "zh": "短信服务超时。请检查网络连接后重试。",
            "en": "SMS service timeout. Please check your network connection and try again.",
            "az": "SMS xidməti vaxtı bitdi. Şəbəkə bağlantınızı yoxlayın və yenidən cəhd edin."
        },
        "sms_error_auth_failed": {
            "zh": "短信服务认证失败。请联系技术支持。",
            "en": "SMS authentication verification failed. Please contact support.",
            "az": "SMS autentifikasiya yoxlanışı uğursuz oldu. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_unknown": {
            "zh": "短信服务遇到未知错误。请稍后重试或联系技术支持。",
            "en": "SMS service encountered an unknown error. Please try again later or contact support.",
            "az": "SMS xidməti naməlum xəta ilə üzləşdi. Daha sonra yenidən cəhd edin və ya dəstəklə əlaqə saxlayın."
        },
        # SMS Error Codes - InvalidParameterValue
        "sms_error_content_too_long": {
            "zh": "短信内容过长。请联系技术支持。",
            "en": "SMS content is too long. Please contact support.",
            "az": "SMS məzmunu çox uzundur. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_invalid_phone": {
            "zh": "手机号格式无效。请检查您输入的是有效的手机号。",
            "en": "Invalid phone number format. Please check that you entered a valid mobile number.",
            "az": "Etibarsız telefon nömrəsi formatı. Etibarlı mobil nömrə daxil etdiyinizi yoxlayın."
        },
        "sms_error_url_prohibited": {
            "zh": "短信模板参数中不允许使用URL。请联系技术支持。",
            "en": "URL is not allowed in SMS template parameters. Please contact support.",
            "az": "URL SMS şablon parametrlərində icazə verilmir. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_sdk_app_id_not_exist": {
            "zh": "短信服务配置错误。请联系技术支持。",
            "en": "SMS service configuration error. Please contact support.",
            "az": "SMS xidməti konfiqurasiyası xətası. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_template_param_format": {
            "zh": "短信验证码格式错误。请联系技术支持。",
            "en": "SMS verification code format error. Please contact support.",
            "az": "SMS təsdiq kodu formatı xətası. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_template_param_length": {
            "zh": "短信模板参数超过长度限制。请联系技术支持。",
            "en": "SMS template parameter exceeds length limit. Please contact support.",
            "az": "SMS şablon parametri uzunluq limitini aşır. Dəstəklə əlaqə saxlayın."
        },
        # SMS Error Codes - LimitExceeded
        "sms_error_daily_limit_country": {
            "zh": "该国家/地区今日短信发送次数已达上限。请明天再试或联系技术支持。",
            "en": "Daily SMS limit reached for this country/region. Please try again tomorrow or contact support.",
            "az": "Bu ölkə/bölgə üçün günlük SMS limiti çatdı. Sabah yenidən cəhd edin və ya dəstəklə əlaqə saxlayın."
        },
        "sms_error_country_restricted": {
            "zh": "该国家/地区短信发送受限。请联系技术支持。",
            "en": "SMS sending to this country/region is restricted. Please contact support.",
            "az": "Bu ölkə/bölgəyə SMS göndərmə məhdudlaşdırılıb. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_daily_limit": {
            "zh": "今日短信发送次数已达上限。请明天再试或联系技术支持。",
            "en": "Daily SMS limit reached. Please try again tomorrow or contact support.",
            "az": "Günlük SMS limiti çatdı. Sabah yenidən cəhd edin və ya dəstəklə əlaqə saxlayın."
        },
        "sms_error_international_daily_limit": {
            "zh": "今日国际短信发送次数已达上限。请明天再试或联系技术支持。",
            "en": "Daily international SMS limit reached. Please try again tomorrow or contact support.",
            "az": "Günlük beynəlxalq SMS limiti çatdı. Sabah yenidən cəhd edin və ya dəstəklə əlaqə saxlayın."
        },
        "sms_error_mainland_daily_limit": {
            "zh": "今日中国大陆短信发送次数已达上限。请明天再试或联系技术支持。",
            "en": "Daily mainland China SMS limit reached. Please try again tomorrow or contact support.",
            "az": "Günlük Çin materiki SMS limiti çatdı. Sabah yenidən cəhd edin və ya dəstəklə əlaqə saxlayın."
        },
        "sms_error_frequency_limit": {
            "zh": "短信发送频率限制。请稍后重试。",
            "en": "SMS frequency limit reached. Please wait and try again later.",
            "az": "SMS tezliyi limiti çatdı. Gözləyin və daha sonra yenidən cəhd edin."
        },
        "sms_error_phone_count_limit": {
            "zh": "单次请求中手机号数量过多（最多200个）。请联系技术支持。",
            "en": "Too many phone numbers in one request (maximum 200). Please contact support.",
            "az": "Bir sorğuda çox sayda telefon nömrəsi (maksimum 200). Dəstəklə əlaqə saxlayın."
        },
        "sms_error_phone_daily_limit": {
            "zh": (
                "该手机号今日短信发送次数已达上限。请明天再试或联系技术支持。"
            ),
            "en": (
                "Daily SMS limit reached for this phone number. "
                "Please try again tomorrow or contact support."
            ),
            "az": (
                "Bu telefon nömrəsi üçün günlük SMS limiti çatdı. "
                "Sabah yenidən cəhd edin və ya dəstəklə əlaqə saxlayın."
            )
        },
        "sms_error_phone_hourly_limit": {
            "zh": "该手机号每小时短信发送次数已达上限。请稍后再试。",
            "en": "Hourly SMS limit reached for this phone number. Please wait and try again later.",
            "az": "Bu telefon nömrəsi üçün saatlıq SMS limiti çatdı. Gözləyin və daha sonra yenidən cəhd edin."
        },
        "sms_error_phone_same_content_daily": {
            "zh": "该手机号今日发送相同短信内容次数已达上限。请明天再试。",
            "en": "Daily limit reached for sending the same SMS content to this number. Please try again tomorrow.",
            "az": "Bu nömrəyə eyni SMS məzmunu göndərmək üçün günlük limit çatdı. Sabah yenidən cəhd edin."
        },
        "sms_error_phone_thirty_second_limit": {
            "zh": "请等待30秒后再请求新的短信验证码。",
            "en": "Please wait 30 seconds before requesting a new SMS code.",
            "az": "Yeni SMS kodu tələb etməzdən əvvəl 30 saniyə gözləyin."
        },
        # SMS Error Codes - MissingParameter
        "sms_error_empty_phone_list": {
            "zh": "手机号列表为空。请提供有效的手机号。",
            "en": "Phone number list is empty. Please provide a valid phone number.",
            "az": "Telefon nömrəsi siyahısı boşdur. Etibarlı telefon nömrəsi təqdim edin."
        },
        # SMS Error Codes - UnauthorizedOperation
        "sms_error_marketing_permission_denied": {
            "zh": "营销短信权限被拒绝。请联系技术支持。",
            "en": "Marketing SMS permission denied. Please contact support.",
            "az": "Marketinq SMS icazəsi rədd edildi. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_ip_not_whitelisted": {
            "zh": "请求IP不在白名单中。请联系技术支持。",
            "en": "Request IP not in whitelist. Please contact support.",
            "az": "Sorğu IP ağ siyahısında deyil. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_permission_denied": {
            "zh": "短信请求权限被拒绝。请联系技术支持。",
            "en": "SMS request permission denied. Please contact support.",
            "az": "SMS sorğu icazəsi rədd edildi. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_service_disabled": {
            "zh": "短信服务已禁用。请联系技术支持。",
            "en": "SMS service is disabled. Please contact support.",
            "az": "SMS xidməti deaktivdir. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_service_suspended": {
            "zh": "短信服务因欠费已暂停。请联系技术支持。",
            "en": "SMS service suspended due to unpaid balance. Please contact support.",
            "az": "SMS xidməti ödəniş olunmamış balans səbəbindən dayandırılıb. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_auth_verify_failed": {
            "zh": "短信服务认证错误。请联系技术支持。",
            "en": "SMS service authentication error. Please contact support.",
            "az": "SMS xidməti autentifikasiya xətası. Dəstəklə əlaqə saxlayın."
        },
        # SMS Error Codes - UnsupportedOperation
        "sms_error_operation_not_supported": {
            "zh": "短信操作不支持。请联系技术支持。",
            "en": "SMS operation not supported. Please contact support.",
            "az": "SMS əməliyyatı dəstəklənmir. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_template_mismatch_domestic": {
            "zh": "国内短信模板不能用于国际号码。请联系技术支持。",
            "en": "Domestic SMS template cannot be used for international numbers. Please contact support.",
            "az": "Daxili SMS şablonu beynəlxalq nömrələr üçün istifadə edilə bilməz. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_mixed_phone_types": {
            "zh": "不能在同一请求中同时发送到国内和国际号码。请联系技术支持。",
            "en": "Cannot send to both domestic and international numbers in one request. Please contact support.",
            "az": "Bir sorğuda həm daxili, həm də beynəlxalq nömrələrə göndərilə bilməz. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_template_mismatch_international": {
            "zh": "国际短信模板不能用于国内号码。请联系技术支持。",
            "en": "International SMS template cannot be used for domestic numbers. Please contact support.",
            "az": "Beynəlxalq SMS şablonu daxili nömrələr üçün istifadə edilə bilməz. Dəstəklə əlaqə saxlayın."
        },
        "sms_error_region_not_supported": {
            "zh": "不支持向该地区发送短信。请联系技术支持。",
            "en": "SMS sending to this region is not supported. Please contact support.",
            "az": "Bu bölgəyə SMS göndərmə dəstəklənmir. Dəstəklə əlaqə saxlayın."
        },
        # SMS Error Codes - Generic fallback
        "sms_error_generic": {
            "zh": (
                "短信发送失败：{}。请稍后重试，如果问题持续存在，请联系技术支持。"
            ),
            "en": (
                "SMS sending failed due to: {}. Please try again later or "
                "contact support if the problem persists."
            ),
            "az": (
                "SMS göndərmə uğursuz oldu: {}. Daha sonra yenidən cəhd edin "
                "və ya problem davam edərsə dəstəklə əlaqə saxlayın."
            )
        },
        "invalid_passkey": {
            "zh": "无效的密钥",
            "en": "Invalid passkey",
            "az": "Etibarsız passkey"
        },
        "admin_access_required": {
            "zh": "需要管理员权限",
            "en": "Admin access required",
            "az": "İdarəçi girişi tələb olunur"
        },
        "manager_access_required": {
            "zh": "需要管理员权限",
            "en": "Manager access required",
            "az": "Menecer girişi tələb olunur"
        },
        "elevated_access_required": {
            "zh": "需要管理员或管理者权限",
            "en": "Admin or manager access required",
            "az": "İdarəçi və ya menecer girişi tələb olunur"
        },
        "missing_required_fields": {
            "zh": "缺少必填字段：{}",
            "en": "Missing required fields: {}",
            "az": "Tələb olunan sahələr çatışmır: {}"
        },
        "organization_exists": {
            "zh": "组织 '{}' 已存在",
            "en": "Organization '{}' exists",
            "az": "Təşkilat '{}' mövcuddur"
        },
        "failed_generate_invitation_code": {
            "zh": "生成唯一邀请码失败",
            "en": "Failed to generate unique invitation code",
            "az": "Unikal dəvət kodu yaratmaq mümkün olmadı"
        },
        "organization_not_found": {
            "zh": "未找到组织 ID {}",
            "en": "Organization ID {} not found",
            "az": "Təşkilat ID {} tapılmadı"
        },
        "organization_code_empty": {
            "zh": "组织代码不能为空",
            "en": "Organization code cannot be empty",
            "az": "Təşkilat kodu boş ola bilməz"
        },
        "organization_code_too_long": {
            "zh": "组织代码过长（最多50个字符）",
            "en": "Organization code too long (max 50)",
            "az": "Təşkilat kodu çox uzundur (maksimum 50)"
        },
        "invalid_date_format": {
            "zh": "日期格式无效。请使用 ISO 格式 (YYYY-MM-DD)",
            "en": "Invalid date format. Use ISO format (YYYY-MM-DD)",
            "az": "Etibarsız tarix formatı. ISO formatından istifadə edin (YYYY-MM-DD)"
        },
        "cannot_delete_organization_with_users": {
            "zh": "无法删除拥有 {} 个用户的组织",
            "en": "Cannot delete organization with {} users",
            "az": "{} istifadəçisi olan təşkilatı silmək mümkün deyil"
        },
        "user_not_found": {
            "zh": "未找到用户 ID {}",
            "en": "User ID {} not found",
            "az": "İstifadəçi ID {} tapılmadı"
        },
        "user_not_in_organization": {
            "zh": "用户不属于该组织",
            "en": "User does not belong to this organization",
            "az": "İstifadəçi bu təşkilata aid deyil"
        },
        "phone_cannot_be_empty": {
            "zh": "手机号不能为空",
            "en": "Phone cannot be empty",
            "az": "Telefon boş ola bilməz"
        },
        "phone_format_invalid": {
            "zh": "手机号必须是11位数字，以1开头",
            "en": "Phone must be 11 digits starting with 1",
            "az": "Telefon 1 ilə başlayan 11 rəqəm olmalıdır"
        },
        "phone_already_registered_other": {
            "zh": "手机号 {} 已被其他用户注册",
            "en": "Phone number {} is already registered by another user",
            "az": "Telefon nömrəsi {} artıq başqa istifadəçi tərəfindən qeydiyyatdan keçib"
        },
        "phone_same_as_current": {
            "zh": "新手机号与当前手机号相同，无需更改",
            "en": "New phone number is the same as current phone number",
            "az": "Yeni telefon nömrəsi cari nömrə ilə eynidir"
        },
        "phone_already_in_use": {
            "zh": "该手机号已被其他用户使用",
            "en": "This phone number is already in use by another user",
            "az": "Bu telefon nömrəsi artıq başqa istifadəçi tərəfindən istifadə olunur"
        },
        "name_too_short": {
            "zh": "姓名至少需要2个字符",
            "en": "Name must be at least 2 characters",
            "az": "Ad ən azı 2 simvol olmalıdır"
        },
        "name_cannot_contain_numbers": {
            "zh": "姓名不能包含数字",
            "en": "Name cannot contain numbers",
            "az": "Ad rəqəmlər ehtiva edə bilməz"
        },
        "cannot_delete_own_account": {
            "zh": "无法删除您自己的账户",
            "en": "Cannot delete your own account",
            "az": "Öz hesabınızı silmək mümkün deyil"
        },
        "cannot_reset_own_password": {
            "zh": "无法重置您自己的密码",
            "en": "Cannot reset your own password",
            "az": "Öz parolunuzu sıfırlaya bilməzsiniz"
        },
        "password_cannot_be_empty": {
            "zh": "密码不能为空",
            "en": "Password cannot be empty",
            "az": "Parol boş ola bilməz"
        },
        "password_too_short": {
            "zh": "密码长度至少需要8个字符",
            "en": "Password must be at least 8 characters long",
            "az": "Parol ən azı 8 simvol uzunluğunda olmalıdır"
        },
        "cannot_modify_field_via_api": {
            "zh": "无法通过 API 修改 {}",
            "en": "Cannot modify {} via API",
            "az": "API vasitəsilə {} dəyişdirmək mümkün deyil"
        },
        "name_required": {
            "zh": "姓名是必填项",
            "en": "Name is required",
            "az": "Ad tələb olunur"
        },
        "api_key_not_found": {
            "zh": "未找到 API 密钥",
            "en": "API key not found",
            "az": "API açarı tapılmadı"
        },
        "user_creation_failed": {
            "zh": "用户创建失败：{}",
            "en": "User creation failed: {}",
            "az": "İstifadəçi yaratmaq mümkün olmadı: {}"
        },
        "no_organizations_available": {
            "zh": "没有可用的组织",
            "en": "No organizations available",
            "az": "Mövcud təşkilat yoxdur"
        },
        "invalid_password_change": {
            "zh": "当前密码不正确",
            "en": "Current password is incorrect",
            "az": "Cari parol yanlışdır"
        },
        "password_same_as_current": {
            "zh": "新密码不能与当前密码相同",
            "en": "New password cannot be the same as current password",
            "az": "Yeni parol cari parolla eyni ola bilməz"
        },
        "avatar_not_found": {
            "zh": "头像未找到",
            "en": "Avatar not found",
            "az": "Avatar tapılmadı"
        }
    }

    # Success Messages
    SUCCESS = {
        "diagram_generated": {
            "zh": "图示生成成功",
            "en": "Diagram generated successfully",
            "az": "Diaqram uğurla yaradıldı"
        },
        "diagram_exported": {
            "zh": "图示已导出",
            "en": "Diagram exported",
            "az": "Diaqram ixrac edildi"
        },
        "request_processed": {
            "zh": "请求已处理",
            "en": "Request processed",
            "az": "Sorğu emal edildi"
        },
        "verification_code_sent": {
            "zh": "验证码发送成功",
            "en": "Verification code sent successfully",
            "az": "Təsdiq kodu uğurla göndərildi"
        },
        "verification_code_valid": {
            "zh": "验证码有效",
            "en": "Verification code is valid",
            "az": "Təsdiq kodu etibarlıdır"
        },
        "password_reset_success": {
            "zh": "密码重置成功",
            "en": "Password reset successfully",
            "az": "Parol uğurla sıfırlandı"
        },
        "password_reset_for_user": {
            "zh": "用户 {} 的密码重置成功",
            "en": "Password reset successfully for user {}",
            "az": "İstifadəçi {} üçün parol uğurla sıfırlandı"
        },
        "logged_out": {
            "zh": "已成功退出登录",
            "en": "Logged out successfully",
            "az": "Uğurla çıxış edildi"
        },
        "organization_deleted": {
            "zh": "组织 {} 已成功删除",
            "en": "Organization {} deleted successfully",
            "az": "Təşkilat {} uğurla silindi"
        },
        "manager_role_set": {
            "zh": "已将 {} 设置为管理员",
            "en": "{} has been set as manager",
            "az": "{} menecer olaraq təyin edildi"
        },
        "manager_role_removed": {
            "zh": "已移除 {} 的管理员权限",
            "en": "Manager role removed from {}",
            "az": "{} üçün menecer rolu silindi"
        },
        "user_updated": {
            "zh": "用户更新成功",
            "en": "User updated successfully",
            "az": "İstifadəçi uğurla yeniləndi"
        },
        "user_deleted": {
            "zh": "用户 {} 已成功删除",
            "en": "User {} deleted successfully",
            "az": "İstifadəçi {} uğurla silindi"
        },
        "password_change_success": {
            "zh": "密码修改成功",
            "en": "Password changed successfully",
            "az": "Parol uğurla dəyişdirildi"
        },
        "avatar_update_success": {
            "zh": "头像更新成功",
            "en": "Avatar updated successfully",
            "az": "Avatar uğurla yeniləndi"
        },
        "phone_changed_success": {
            "zh": "手机号更换成功",
            "en": "Phone number changed successfully",
            "az": "Telefon nömrəsi uğurla dəyişdirildi"
        },
        "user_unlocked": {
            "zh": "用户 {} 已成功解锁",
            "en": "User {} unlocked successfully",
            "az": "İstifadəçi {} uğurla kilidlənmədi"
        },
        "settings_updated": {
            "zh": "设置更新成功",
            "en": "Settings updated successfully",
            "az": "Parametrlər uğurla yeniləndi"
        },
        "api_key_created": {
            "zh": "API 密钥创建成功",
            "en": "API key created successfully",
            "az": "API açarı uğurla yaradıldı"
        },
        "api_key_updated": {
            "zh": "API 密钥更新成功",
            "en": "API key updated successfully",
            "az": "API açarı uğurla yeniləndi"
        },
        "api_key_activated": {
            "zh": "API 密钥 '{}' 已激活",
            "en": "API key '{}' activated",
            "az": "API açarı '{}' aktivləşdirildi"
        },
        "api_key_deactivated": {
            "zh": "API 密钥 '{}' 已停用",
            "en": "API key '{}' deactivated",
            "az": "API açarı '{}' deaktivləşdirildi"
        }
    }

    # Warning Messages
    WARNINGS = {
        "slow_request": {
            "zh": "请求处理较慢",
            "en": "Slow request processing",
            "az": "Yavaş sorğu emalı"
        },
        "deprecated_endpoint": {
            "zh": "此端点已废弃",
            "en": "This endpoint is deprecated",
            "az": "Bu endpoint köhnəlmişdir"
        },
        "server_restart_required": {
            "zh": "需要重启服务器才能使更改生效！",
            "en": "Server restart required for changes to take effect!",
            "az": "Dəyişikliklərin qüvvəyə minməsi üçün serveri yenidən başlatmaq lazımdır!"
        },
        "api_key_save_warning": {
            "zh": "请安全保存此密钥 - 它不会再次显示！",
            "en": "Save this key securely - it won't be shown again!",
            "az": "Bu açarı təhlükəsiz saxlayın - yenidən göstərilməyəcək!"
        }
    }

    @classmethod
    def get(cls, category: str, key: str, *args, lang: Language = "en") -> str:
        """
        Get a message in the specified language.

        Args:
            category: Message category ('ERRORS', 'SUCCESS', 'WARNINGS')
            key: Message key
            *args: Format arguments for messages with placeholders.
                   If first arg is a language code ('zh', 'en', 'az'),
                   it will be used as lang and removed from args.
            lang: Language ('zh', 'en', or 'az'). Keyword-only parameter.

        Returns:
            Localized message string
        """
        # Backward compatibility: check if first arg is a language code
        format_args = list(args)
        if format_args and isinstance(format_args[0], str):
            potential_lang = format_args[0].lower()
            if potential_lang == "zh":
                lang = "zh"
                format_args = format_args[1:]
            elif potential_lang == "en":
                lang = "en"
                format_args = format_args[1:]
            elif potential_lang == "az":
                lang = "az"
                format_args = format_args[1:]

        messages = getattr(cls, category, {})
        message_dict = messages.get(key, {})
        # Fallback order: requested lang -> en -> key
        message = message_dict.get(lang) or message_dict.get("en") or key

        # Format message if arguments provided
        if format_args:
            try:
                return message.format(*format_args)
            except (IndexError, KeyError):
                return message

        return message

    @classmethod
    def error(cls, key: str, *args, lang: Language = "en") -> str:
        """Get an error message"""
        return cls.get("ERRORS", key, *args, lang=lang)

    @classmethod
    def success(cls, key: str, *args, lang: Language = "en") -> str:
        """Get a success message"""
        return cls.get("SUCCESS", key, *args, lang=lang)

    @classmethod
    def warning(cls, key: str, *args, lang: Language = "en") -> str:
        """Get a warning message"""
        return cls.get("WARNINGS", key, *args, lang=lang)


# Convenience function for getting language from request
def get_request_language(
    language_header: Optional[str] = None,
    accept_language: Optional[str] = None
) -> Language:
    """
    Determine language from request headers.

    Args:
        language_header: Custom X-Language header
        accept_language: Accept-Language header

    Returns:
        'zh', 'en', or 'az'
    """
    # Priority 1: Custom X-Language header
    if language_header:
        lang = language_header.lower()
        if lang in ["zh", "zh-cn", "zh-tw", "chinese"]:
            return "zh"
        if lang in ["az", "azeri", "azerbaijani", "azərbaycan"]:
            return "az"
        return "en"

    # Priority 2: Accept-Language header
    if accept_language:
        lang = accept_language.lower()
        if any(x in lang for x in ["zh", "chinese"]):
            return "zh"
        if any(x in lang for x in ["az", "azeri", "azerbaijani", "azərbaycan"]):
            return "az"

    # Default: English
    return "en"