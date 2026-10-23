"""
Startup gate for required ``.env`` values.

Prints a console banner and exits when diagram generation, the MindMate user
id, or an enabled feature flag is missing the settings it needs. Same shape as
the LibreOffice and Playwright startup notices.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

from config.settings import config
from services.auth.tsec.config import (
    PROVIDER_TSEC,
    requested_captcha_provider,
    tencent_captcha_app_id,
    tencent_captcha_app_secret_key,
    tencent_captcha_secret_id,
    tencent_captcha_secret_key,
)
from services.features.vod.credentials import vod_credentials_configured
from services.infrastructure.process.fatal_process_exit import fatal_startup_exit
from services.markets.alipay_certs import cert_bundle_present
from services.markets.alipay_settings import resolve_alipay_cert_dir
from utils.dify_mindmate_user_id import describe_mindmate_dify_user_prefix_error

logger = logging.getLogger(__name__)

_BANNER = "=" * 80
_TEMPLATE_BITS = (
    "change-me",
    "changeme",
    "replace-me",
    "placeholder",
    "your-workspace-api-key-here",
    "your-ark-api-key-here",
    "your_dify_api_key_here",
    "your_dify_backup_api_key_here",
    "your-tencent-secret-id-here",
    "your-tencent-secret-key-here",
    "llm-your-workspace-id",
    "dev_yourname",
    "ep-20250101000000-dummy",
    "your-domain.com",
)
_ENTERPRISE_ACK = "I_UNDERSTAND_PUBLIC_EXPOSURE_RISK"


@dataclass(frozen=True)
class StartupEnvGap:
    """One block of missing ``.env`` settings."""

    title: str
    lines: tuple[str, ...]


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("true", "1", "yes")


def _debug_mode() -> bool:
    return _truthy("DEBUG", "False")


def _raw(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _is_template(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(token in lowered for token in _TEMPLATE_BITS)


def _unusable(name: str) -> bool:
    return _is_template(_raw(name))


def _llm_gap() -> StartupEnvGap | None:
    """DashScope and Volcengine values ClientManager needs before the first diagram."""
    missing: list[str] = []
    if _unusable("QWEN_API_KEY"):
        missing.append("QWEN_API_KEY — DashScope workspace apiKey")
    explicit_url = _raw("QWEN_API_URL") or _raw("DASHSCOPE_API_URL")
    if not explicit_url and _unusable("DASHSCOPE_WORKSPACE_ID"):
        missing.append("DASHSCOPE_WORKSPACE_ID — workspace id, or set QWEN_API_URL")
    if _unusable("ARK_API_KEY"):
        missing.append("ARK_API_KEY — Volcengine key for DeepSeek, GLM Flash, and Doubao")
    if _unusable("ARK_DEEPSEEK_ENDPOINT"):
        missing.append("ARK_DEEPSEEK_ENDPOINT — replace ep-20250101000000-dummy with the console endpoint")
    if _unusable("ARK_DOUBAO_ENDPOINT"):
        missing.append("ARK_DOUBAO_ENDPOINT — replace ep-20250101000000-dummy with the console endpoint")
    if _unusable("GLM_FLASH_MODEL"):
        missing.append("GLM_FLASH_MODEL — Volcengine model id, for example glm-5-3-flash-260828")
    if _unusable("DOUBAO_MODEL"):
        missing.append("DOUBAO_MODEL — Volcengine model id, for example doubao-seed-2-1-turbo-260628")
    if not missing:
        return None
    lines = (
        "Diagram generation reads these from .env. Replace the samples from env.example.",
        *(f"  {item}" for item in missing),
    )
    return StartupEnvGap("LLM", lines)


def _mindmate_prefix_gap() -> StartupEnvGap | None:
    """MindMate stores chats as ``<prefix>_mg_user_<id>``. ``/auth/mode`` requires the prefix."""
    error = describe_mindmate_dify_user_prefix_error()
    if error is None:
        return None
    return StartupEnvGap(
        "MindMate user id",
        (
            error,
            "  MINDMATE_DIFY_USER_PREFIX=dev_roy",
            "  A school install uses a stable name, such as bayi.",
            "  Leave the value unchanged after chats exist under it.",
        ),
    )


def _mindmate_dify_gap() -> StartupEnvGap | None:
    if not _truthy("FEATURE_MINDMATE"):
        return None
    if not _unusable("DIFY_API_KEY") and not _unusable("DIFY_API_URL"):
        return None
    return StartupEnvGap(
        "FEATURE_MINDMATE",
        (
            "MindMate is on, and the Dify main server pair is missing.",
            "  DIFY_API_KEY=<workflow key>",
            "  DIFY_API_URL=http://dify.mindspringedu.com/v1",
            "  Or set FEATURE_MINDMATE=False",
        ),
    )


def _smart_response_gap() -> StartupEnvGap | None:
    if not _truthy("FEATURE_SMART_RESPONSE"):
        return None
    if not _unusable("DEVICE_REGISTRATION_SECRET"):
        return None
    return StartupEnvGap(
        "FEATURE_SMART_RESPONSE",
        (
            "Smart Response is on. ESP32 registration needs a shared secret.",
            "  DEVICE_REGISTRATION_SECRET=<long random secret>",
            "  Or set FEATURE_SMART_RESPONSE=False",
        ),
    )


def _oauth_gaps() -> list[StartupEnvGap]:
    gaps: list[StartupEnvGap] = []
    wechat_on = _truthy("FEATURE_WECHAT_LOGIN")
    dingtalk_on = _truthy("FEATURE_DINGTALK_LOGIN")
    if wechat_on and (_unusable("WECHAT_OAUTH_APP_ID") or _unusable("WECHAT_OAUTH_APP_SECRET")):
        gaps.append(
            StartupEnvGap(
                "FEATURE_WECHAT_LOGIN",
                (
                    "WeChat QR login is on. Set both platform credentials, or turn the flag off.",
                    "  WECHAT_OAUTH_APP_ID=<Open Platform AppID>",
                    "  WECHAT_OAUTH_APP_SECRET=<Open Platform AppSecret>",
                    "  Or set FEATURE_WECHAT_LOGIN=False",
                ),
            )
        )
    if (wechat_on or dingtalk_on) and _unusable("EXTERNAL_BASE_URL"):
        gaps.append(
            StartupEnvGap(
                "OAuth public URL",
                (
                    "QR login needs the public HTTPS origin for redirect URIs.",
                    "  EXTERNAL_BASE_URL=https://mg.mindspringedu.com",
                    "  Or set FEATURE_WECHAT_LOGIN=False and FEATURE_DINGTALK_LOGIN=False",
                ),
            )
        )
    return gaps


def _markets_gap() -> StartupEnvGap | None:
    if not _truthy("FEATURE_MARKETS"):
        return None
    missing: list[str] = []
    app_id = _raw("ALIPAY_APP_ID")
    if _unusable("ALIPAY_APP_ID"):
        missing.append("ALIPAY_APP_ID")
    if _unusable("ALIPAY_NOTIFY_BASE_URL"):
        missing.append("ALIPAY_NOTIFY_BASE_URL=https://your-public-host")
    keys_ready = not _unusable("ALIPAY_APP_PRIVATE_KEY") and not _unusable("ALIPAY_ALIPAY_PUBLIC_KEY")
    certs_ready = bool(app_id) and not _is_template(app_id) and cert_bundle_present(resolve_alipay_cert_dir(), app_id)
    if not keys_ready and not certs_ready:
        missing.append("data/alipay-certs/ (or ALIPAY_APP_PRIVATE_KEY + ALIPAY_ALIPAY_PUBLIC_KEY)")
    if not missing:
        return None
    return StartupEnvGap(
        "FEATURE_MARKETS",
        (
            "Markets checkout is on. Alipay 电脑网站支付 needs these in .env.",
            *(f"  {item}" for item in missing),
            "  Or set FEATURE_MARKETS=False",
        ),
    )


def _vod_gap() -> StartupEnvGap | None:
    if not _truthy("FEATURE_VOD"):
        return None
    if vod_credentials_configured() and not _vod_secrets_are_templates():
        return None
    return StartupEnvGap(
        "FEATURE_VOD",
        (
            "The online video library is on. Tencent VOD credentials are missing.",
            "  TENCENT_VOD_APP_ID=<VOD SubAppId>",
            "  TENCENT_VOD_PLAY_KEY=<default distribution play key>",
            "  TENCENT_VOD_SECRET_ID / TENCENT_VOD_SECRET_KEY",
            "    (or TENCENT_SMS_SECRET_ID / TENCENT_SMS_SECRET_KEY)",
            "  Or set FEATURE_VOD=False",
        ),
    )


def _vod_secrets_are_templates() -> bool:
    """True when VOD would accept env.example placeholder CAM keys."""
    secret_id = _raw("TENCENT_VOD_SECRET_ID") or _raw("TENCENT_SMS_SECRET_ID")
    secret_key = _raw("TENCENT_VOD_SECRET_KEY") or _raw("TENCENT_SMS_SECRET_KEY")
    play_key = _raw("TENCENT_VOD_PLAY_KEY")
    app_id = _raw("TENCENT_VOD_APP_ID")
    return any(_is_template(value) for value in (secret_id, secret_key, play_key, app_id))


def _workshop_gap() -> StartupEnvGap | None:
    if not _truthy("FEATURE_WORKSHOP_CHAT"):
        return None
    if not _truthy("WS_REDIS_FANOUT_ENABLED", "true"):
        return None
    if not _unusable("COLLAB_FANOUT_ORIGIN_SECRET"):
        return None
    return StartupEnvGap(
        "FEATURE_WORKSHOP_CHAT",
        (
            "Workshop Chat is on and WebSocket fan-out is on.",
            "  COLLAB_FANOUT_ORIGIN_SECRET=<shared secret, same on every worker>",
            "  Or set FEATURE_WORKSHOP_CHAT=False",
            "  Or set WS_REDIS_FANOUT_ENABLED=false for a single worker",
        ),
    )


def _captcha_gap() -> StartupEnvGap | None:
    """Production keeps T-Sec. Debug falls back to the SVG captcha when keys are absent."""
    if _debug_mode():
        return None
    if requested_captcha_provider() != PROVIDER_TSEC:
        return None
    values = (
        tencent_captcha_app_id(),
        tencent_captcha_app_secret_key(),
        tencent_captcha_secret_id(),
        tencent_captcha_secret_key(),
    )
    if all(values) and not any(_is_template(value) for value in values):
        return None
    return StartupEnvGap(
        "Captcha",
        (
            "CAPTCHA_PROVIDER=tsec needs Tencent console keys in production.",
            "  TENCENT_CAPTCHA_APP_ID",
            "  TENCENT_CAPTCHA_APP_SECRET_KEY",
            "  TENCENT_CAPTCHA_SECRET_ID / TENCENT_CAPTCHA_SECRET_KEY",
            "    (or TENCENT_SMS_SECRET_ID / TENCENT_SMS_SECRET_KEY)",
            "  Local debug can set CAPTCHA_PROVIDER=legacy instead.",
        ),
    )


def _auth_mode() -> str:
    return (_raw("AUTH_MODE") or "standard").lower()


def _auth_mode_gap() -> StartupEnvGap | None:
    mode = _auth_mode()
    if mode == "bayi" and _is_template(_raw("BAYI_DECRYPTION_KEY")):
        return StartupEnvGap(
            "AUTH_MODE=bayi",
            (
                "Bayi login needs the key issued by 小致. Do not generate a replacement.",
                "  BAYI_DECRYPTION_KEY=<value from 小致>",
                "  Or set AUTH_MODE=standard",
            ),
        )
    if _debug_mode() or mode != "enterprise":
        return None
    if _raw("ENTERPRISE_MODE_PUBLIC_ACK") == _ENTERPRISE_ACK:
        return None
    return StartupEnvGap(
        "AUTH_MODE=enterprise",
        (
            "Enterprise mode disables JWT checks. Confirm that on purpose.",
            f"  ENTERPRISE_MODE_PUBLIC_ACK={_ENTERPRISE_ACK}",
            "  Or set AUTH_MODE=standard",
        ),
    )


def _database_gap() -> StartupEnvGap | None:
    if _debug_mode() or _raw("DATABASE_URL"):
        return None
    return StartupEnvGap(
        "Database",
        (
            "Production needs an explicit database URL.",
            "  DATABASE_URL=postgresql://mindgraph_user:password@localhost:5432/mindgraph",
        ),
    )


def collect_startup_env_gaps() -> list[StartupEnvGap]:
    """Return every ``.env`` gap that should stop startup."""
    config.refresh_env_cache()
    gaps: list[StartupEnvGap | None] = [
        _database_gap(),
        _llm_gap(),
        _mindmate_prefix_gap(),
        _mindmate_dify_gap(),
        _smart_response_gap(),
        _markets_gap(),
        _vod_gap(),
        _workshop_gap(),
        _captcha_gap(),
        _auth_mode_gap(),
    ]
    found = [gap for gap in gaps if gap is not None]
    found.extend(_oauth_gaps())
    return found


def startup_env_requirement_lines(gaps: list[StartupEnvGap] | None = None) -> list[str]:
    """Banner lines. Pass ``gaps`` to avoid collecting twice."""
    items = collect_startup_env_gaps() if gaps is None else gaps
    if not items:
        return []
    lines = [
        _BANNER,
        "[ERROR] MindGraph cannot start until these .env settings are in place.",
        "        Open .env (copy env.example if you do not have one) and set each block below.",
        _BANNER,
        "",
    ]
    for gap in items:
        lines.append(f"  {gap.title}")
        lines.extend(f"    {line}" if line else "" for line in gap.lines)
        lines.append("")
    lines.extend(
        [
            "  cp env.example .env",
            "  Redis, PostgreSQL, Qdrant, Celery, LibreOffice, and Playwright",
            "  are checked next and print their own install steps.",
            "  Full cheatsheet: python -m services.infrastructure.utils.launch_commands",
            _BANNER,
        ]
    )
    return lines


def enforce_startup_env_requirements_or_exit(*, use_fatal_exit: bool = False) -> None:
    """
    Print the banner and stop the process when required ``.env`` values are missing.

    ``use_fatal_exit`` is for Uvicorn workers. The launcher uses ``sys.exit``.
    """
    gaps = collect_startup_env_gaps()
    if not gaps:
        return
    lines = startup_env_requirement_lines(gaps)
    print()
    for line in lines:
        print(line)
        logger.error("[STARTUP] %s", line)
    print()
    if use_fatal_exit:
        fatal_startup_exit(1)
    sys.exit(1)
