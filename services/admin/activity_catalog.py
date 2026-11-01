"""
Classify management-panel writes into stable admin-activity action keys.

Scope is privileged operators only (superadmin, platform_bd, expert,
school_admin). Regular product use — diagrams, chat, teacher class tools —
is not an admin activity even when the same person also holds a panel role.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Optional

_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_PREFIXES = (
    "/api/auth/admin/",
    "/api/mindbot/admin/",
    "/api/library/admin/",
    "/api/learning-space/admin/",
    "/api/vod/",
    "/api/admin/",
)

_EXACT_PATHS = frozenset(
    {
        "/api/auth/quick-register/open",
        "/api/auth/quick-register/close",
    }
)

# Library catalog writes live outside /api/library/admin/. Bookmarks and danmaku do not.
_LIBRARY_ADMIN_WRITE = re.compile(
    r"^/api/library/(?:books/register(?:-batch)?|documents/\d+(?:/(?:cover|visibility))?)$"
)
# Smart Response assign/unassign. Device self-registration is not an admin write.
_DEVICE_ASSIGN = re.compile(r"^/api/devices/[^/]+/assign$")

_SKIP_FRAGMENTS = (
    "health",
    "/validate",
    "analyze-dump",
    "/preview",
)

_SECRET_MARKERS = (
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "ACCESS_KEY",
    "PASSKEY",
    "PRIVATE",
    "AUTHORIZATION",
    "CREDENTIAL",
    "COOKIE",
    "DSN",
    "PWD",
)

_BROAD_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/api/vod/", "vod.change"),
    ("/api/auth/admin/showcase/", "showcase.change"),
    ("/api/library/", "library.change"),
    ("/api/auth/admin/thinking-coins/", "thinking_coins.change"),
    ("/api/auth/admin/teaching-design-template", "teaching_design.change"),
    ("/api/auth/admin/user-dropdown", "user_dropdown.change"),
    ("/api/auth/admin/teacher-usage/", "teacher_usage.change"),
    ("/api/auth/admin/kitty-llmops/", "kitty_llmops.change"),
    ("/api/auth/admin/cos/", "cos.change"),
    ("/api/mindbot/admin/", "mindbot.change"),
    ("/api/learning-space/admin/", "learning_space.change"),
    ("/api/admin/mindmate-export/", "mindmate_export.change"),
    ("/api/admin/update-notification", "update_notification.change"),
)

_Rule = tuple[frozenset[str], re.Pattern[str], str]


def _rule(methods: str, pattern: str, action: str) -> _Rule:
    return (frozenset(methods.split()), re.compile(pattern), action)


_RULES: tuple[_Rule, ...] = (
    _rule("POST", r"^/api/auth/admin/organizations$", "organization.create"),
    _rule("PUT", r"^/api/auth/admin/organizations/\d+$", "organization.update"),
    _rule("DELETE", r"^/api/auth/admin/organizations/\d+$", "organization.delete"),
    _rule(
        "POST",
        r"^/api/auth/admin/organizations/\d+/refresh-invitation-code$",
        "organization.invitation_rotate",
    ),
    _rule("PUT", r"^/api/auth/admin/organizations/\d+/managers/\d+$", "organization.manager_add"),
    _rule("DELETE", r"^/api/auth/admin/organizations/\d+/managers/\d+$", "organization.manager_remove"),
    _rule("POST", r"^/api/auth/admin/organizations/\d+/mindmate-avatar$", "organization.avatar"),
    _rule("POST", r"^/api/auth/admin/mobile/organizations/\d+/mindmate-avatar$", "organization.avatar"),
    _rule("PUT", r"^/api/auth/admin/organizations/\d+/oauth-config$", "organization.oauth_update"),
    _rule("PUT", r"^/api/auth/admin/organizations/\d+/expert-bindings$", "organization.expert_binding"),
    _rule("PATCH", r"^/api/auth/admin/mobile/organizations/\d+/branding$", "organization.branding"),
    _rule("POST", r"^/api/auth/admin/school/invitation-code/rotate$", "school.invitation_rotate"),
    _rule("POST", r"^/api/auth/admin/school/users/batch$", "school_user.batch_create"),
    _rule("POST", r"^/api/auth/admin/school/users$", "school_user.create"),
    _rule("PUT", r"^/api/auth/admin/school/users/\d+/unlock$", "school_user.unlock"),
    _rule("PUT", r"^/api/auth/admin/school/users/\d+$", "school_user.update"),
    _rule("DELETE", r"^/api/auth/admin/school/users/\d+$", "school_user.delete"),
    _rule("PUT", r"^/api/auth/admin/users/\d+/reset-password$", "user.password_reset"),
    _rule("PUT", r"^/api/auth/admin/users/\d+/unlock$", "user.unlock"),
    _rule("PUT", r"^/api/auth/admin/users/\d+/role$", "user.role_update"),
    _rule("PUT", r"^/api/auth/admin/users/\d+$", "user.update"),
    _rule("DELETE", r"^/api/auth/admin/users/\d+$", "user.delete"),
    _rule("PUT", r"^/api/auth/admin/feature-org-access$", "feature.access_update"),
    _rule("PUT", r"^/api/auth/admin/env/settings$", "settings.update"),
    _rule("PUT", r"^/api/auth/admin/settings$", "settings.update"),
    _rule("POST", r"^/api/auth/admin/env/reload-runtime$", "settings.reload"),
    _rule("POST", r"^/api/auth/admin/env/restore$", "settings.restore"),
    _rule("POST", r"^/api/auth/admin/api_keys$", "api_key.create"),
    _rule("PUT", r"^/api/auth/admin/api_keys/\d+/toggle$", "api_key.toggle"),
    _rule("PUT", r"^/api/auth/admin/api_keys/\d+$", "api_key.update"),
    _rule("DELETE", r"^/api/auth/admin/api_keys/\d+$", "api_key.delete"),
    _rule("PUT", r"^/api/auth/admin/llm-control$", "llm_control.update"),
    _rule("POST", r"^/api/auth/admin/database/export$", "database.export"),
    _rule("POST", r"^/api/auth/admin/database/import-dump$", "database.import"),
    _rule("POST", r"^/api/auth/admin/database/merge-dump$", "database.merge"),
    _rule("POST", r"^/api/auth/admin/database/cleanup-orphans$", "database.cleanup"),
    _rule("PUT", r"^/api/auth/admin/errors/groups/\d+/mute$", "error_group.mute"),
    _rule("POST", r"^/api/learning-space/admin/pilots$", "learning_space.pilot_create"),
    _rule("PATCH", r"^/api/learning-space/admin/pilots/\d+$", "learning_space.pilot_update"),
    _rule("DELETE", r"^/api/learning-space/admin/pilots/\d+$", "learning_space.pilot_delete"),
    _rule("POST", r"^/api/learning-space/admin/pilots/\d+/delete$", "learning_space.pilot_delete"),
    _rule("POST", r"^/api/learning-space/admin/classes$", "learning_space.class_create"),
    _rule("PATCH", r"^/api/learning-space/admin/classes/\d+$", "learning_space.class_update"),
    _rule("POST", r"^/api/learning-space/admin/classes/\d+/rotate-code$", "learning_space.code_rotate"),
    _rule("POST", r"^/api/learning-space/admin/classes/\d+/import", "learning_space.import"),
    _rule("POST", r"^/api/learning-space/admin/classes/\d+/members/\d+/remove$", "learning_space.member_remove"),
    _rule("POST", r"^/api/learning-space/admin/students/\d+/reset-password$", "learning_space.password_reset"),
    _rule("POST", r"^/api/mindbot/admin/configs$", "mindbot.config_create"),
    _rule("PUT", r"^/api/mindbot/admin/configs/\d+$", "mindbot.config_update"),
    _rule("DELETE", r"^/api/mindbot/admin/configs/\d+$", "mindbot.config_delete"),
    _rule("POST", r"^/api/mindbot/admin/configs/\d+/rotate-callback-token$", "mindbot.token_rotate"),
    _rule("POST", r"^/api/auth/quick-register/open$", "quick_register.open"),
    _rule("POST", r"^/api/auth/quick-register/close$", "quick_register.close"),
)


def normalize_activity_path(path: str) -> str:
    """Drop a trailing slash so route patterns stay exact."""
    if len(path) > 1 and path.endswith("/"):
        return path[:-1]
    return path


def _in_scope(path: str) -> bool:
    if path in _EXACT_PATHS:
        return True
    if _LIBRARY_ADMIN_WRITE.match(path) or _DEVICE_ASSIGN.match(path):
        return True
    return any(path.startswith(prefix) for prefix in _PREFIXES)


def _skipped(path: str) -> bool:
    return any(fragment in path for fragment in _SKIP_FRAGMENTS)


def classify_admin_activity(method: str, path: str) -> Optional[str]:
    """Return an action key, or None when this request is not an admin activity."""
    if method not in _MUTATING:
        return None
    normalized = normalize_activity_path(path)
    if not _in_scope(normalized) or _skipped(normalized):
        return None
    for methods, pattern, action in _RULES:
        if method in methods and pattern.match(normalized):
            return action
    for prefix, action in _BROAD_PREFIXES:
        if normalized.startswith(prefix):
            return action
    return "admin.mutate"


def _secret_key(key: str) -> bool:
    upper = key.upper()
    return any(marker in upper for marker in _SECRET_MARKERS)


def _secret_value(text: str) -> bool:
    """Masked placeholders and URLs that embed userinfo must not be stored."""
    if text.startswith("***"):
        return True
    scheme = text.find("://")
    return scheme >= 0 and "@" in text[scheme:]


def _short_value(value: Any) -> str:
    text = str(value)
    if len(text) > 120:
        return text[:117] + "..."
    return text


def public_setting_changes(mapping: Mapping[str, Any]) -> list[dict[str, str]]:
    """Key/value rows safe to store. Secrets are masked."""
    rows: list[dict[str, str]] = []
    for key, value in mapping.items():
        text = str(value)
        shown = "***" if _secret_key(str(key)) or _secret_value(text) else _short_value(value)
        rows.append({"key": str(key), "value": shown})
        if len(rows) >= 60:
            break
    return rows


def feature_flags_only(detail: Optional[Mapping[str, Any]]) -> bool:
    """True when a settings write only flipped FEATURE_* flags."""
    if not detail:
        return False
    changes = detail.get("changes")
    if not isinstance(changes, list) or not changes:
        return False
    saw_flag = False
    for item in changes:
        if not isinstance(item, dict):
            return False
        key = item.get("key")
        if not isinstance(key, str) or not key.startswith("FEATURE_"):
            return False
        saw_flag = True
    return saw_flag


def resolve_admin_action(method: str, path: str, detail: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Classify the route, promoting a feature-flag-only settings write."""
    action = classify_admin_activity(method, path)
    if action == "settings.update" and feature_flags_only(detail):
        return "feature.flag_update"
    return action


def _capped_ints(values: Any, cap: int) -> list[int]:
    rows: list[int] = []
    for item in list(values or []):
        if isinstance(item, bool) or not isinstance(item, int):
            continue
        rows.append(item)
        if len(rows) >= cap:
            break
    return rows


def feature_access_detail(body: Mapping[str, Any]) -> dict[str, Any]:
    """Compact feature-access snapshot. Id lists are capped."""
    rules: list[dict[str, Any]] = []
    for key, entry in body.items():
        rules.append(
            {
                "key": str(key),
                "restrict": bool(getattr(entry, "restrict", False)),
                "organization_ids": _capped_ints(getattr(entry, "organization_ids", None), 30),
                "user_ids": _capped_ints(getattr(entry, "user_ids", None), 30),
            }
        )
        if len(rules) >= 40:
            break
    return {"rules": rules}


def known_admin_activity_actions() -> frozenset[str]:
    """Every action the catalog can emit, including the fallback."""
    actions = {action for _methods, _pattern, action in _RULES}
    actions.update(action for _prefix, action in _BROAD_PREFIXES)
    actions.add("admin.mutate")
    actions.add("feature.flag_update")
    return frozenset(actions)
