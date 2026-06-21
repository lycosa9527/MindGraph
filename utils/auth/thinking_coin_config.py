"""Thinking coin (思维币) default constants and feature flag.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
from typing import Final

THINKING_COIN_SIGNUP_GRANT_DEFAULT: Final[int] = 200
THINKING_COIN_DAILY_EARN_CAP_DEFAULT: Final[int] = 135
THINKING_COIN_COST_MINDMATE_TURN_DEFAULT: Final[int] = 6
THINKING_COIN_COST_DIAGRAM_GEN_DEFAULT: Final[int] = 15
THINKING_COIN_COST_CANVAS_ASSIST_DEFAULT: Final[int] = 4

SETTING_SIGNUP_GRANT: Final[str] = "signup_grant"
SETTING_DAILY_EARN_CAP: Final[str] = "daily_earn_cap"
SETTING_COST_MINDMATE: Final[str] = "cost_mindmate_turn"
SETTING_COST_DIAGRAM: Final[str] = "cost_diagram_gen"
SETTING_COST_CANVAS: Final[str] = "cost_canvas_assist"

LEDGER_SIGNUP_GRANT: Final[str] = "signup_grant"
LEDGER_DAILY_CHECKIN: Final[str] = "daily_checkin"
LEDGER_REFERRAL: Final[str] = "referral_reward"
LEDGER_CASE: Final[str] = "case_reward"
LEDGER_TASK: Final[str] = "task_reward"
LEDGER_SUBSCRIPTION: Final[str] = "subscription_grant"
LEDGER_AI_SPEND: Final[str] = "ai_spend"
LEDGER_ADMIN: Final[str] = "admin_adjust"

HANDLER_AUTO_LOGIN: Final[str] = "auto_login"
HANDLER_USAGE_DAILY: Final[str] = "usage_daily"
HANDLER_CLIENT_EVENT: Final[str] = "client_event"
HANDLER_NAVIGATE: Final[str] = "navigate"
HANDLER_CUSTOM_CTA: Final[str] = "custom_cta"
HANDLER_REFERRAL: Final[str] = "copy_referral_link"

EVENT_MINDMATE_SHARE: Final[str] = "mindmate_share"
EVENT_DIAGRAM_EXPORT: Final[str] = "diagram_export"
EVENT_LEARNING_SHEET: Final[str] = "learning_sheet_enable"
EVENT_DIAGRAM_SAVE: Final[str] = "diagram_save"
EVENT_DIAGRAM_TRANSLATE: Final[str] = "diagram_translate"
EVENT_DIAGRAM_SNAPSHOT: Final[str] = "diagram_snapshot"
EVENT_WORKSHOP_JOIN: Final[str] = "workshop_join"

SLUG_DAILY_MINDMATE_SHARE: Final[str] = "daily_mindmate_share"
SLUG_DAILY_DIAGRAM_EXPORT: Final[str] = "daily_diagram_export"
SLUG_DAILY_LEARNING_SHEET: Final[str] = "daily_learning_sheet"
SLUG_DAILY_DIAGRAM_SAVE: Final[str] = "daily_diagram_save"
SLUG_DAILY_DIAGRAM_TRANSLATE: Final[str] = "daily_diagram_translate"
SLUG_DAILY_DIAGRAM_SNAPSHOT: Final[str] = "daily_diagram_snapshot"
SLUG_DAILY_WORKSHOP_JOIN: Final[str] = "daily_workshop_join"
SLUG_DAILY_LEARNING_SHEET_AI: Final[str] = "daily_learning_sheet_ai"

SLUG_DAILY_CHECKIN: Final[str] = "daily_checkin"
SLUG_DAILY_MINDMATE: Final[str] = "daily_mindmate"
SLUG_DAILY_DIAGRAM: Final[str] = "daily_diagram_ai"
SLUG_PUBLISH_CASE: Final[str] = "publish_case"
SLUG_REFERRAL: Final[str] = "referral_register"

CANVAS_ASSIST_REQUEST_TYPES: Final[frozenset[str]] = frozenset(
    {"autocomplete", "node_palette"}
)


def feature_thinking_coins_enabled() -> bool:
    """True when FEATURE_THINKING_COINS env is enabled."""
    return os.getenv("FEATURE_THINKING_COINS", "False").lower() == "true"
