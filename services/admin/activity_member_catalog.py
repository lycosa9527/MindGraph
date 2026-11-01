"""
Important actions by teachers, students, and personal users.

The management-panel log records these so an operator can see who did what.
Everyday product use — diagram edits, chat, grading, likes, preferences — is
left out on purpose. There is no catch-all: a path is stored only when it
matches a rule below.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Optional

from services.admin.activity_catalog import normalize_activity_path

_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_Rule = tuple[frozenset[str], re.Pattern[str], str]


def _rule(methods: str, pattern: str, action: str) -> _Rule:
    return (frozenset(methods.split()), re.compile(pattern), action)


# First match wins. Keep destructive, security, sharing, and billing paths only.
_RULES: tuple[_Rule, ...] = (
    _rule("PUT", r"^/api/auth/change-password$", "account.password_change"),
    _rule("POST", r"^/api/auth/set-password-with-sms$", "account.password_change"),
    _rule("POST", r"^/api/auth/reset-password$", "account.password_change"),
    _rule("POST", r"^/api/auth/reset-password-email$", "account.password_change"),
    _rule("POST", r"^/api/learning-space/student/change-password$", "account.password_change"),
    _rule("POST", r"^/api/auth/phone/change$", "account.phone_change"),
    _rule("POST", r"^/api/auth/api-token$", "account.api_token_create"),
    _rule("DELETE", r"^/api/auth/api-token$", "account.api_token_revoke"),
    _rule("DELETE", r"^/api/auth/login-devices/[^/]+$", "account.session_revoke"),
    _rule("POST", r"^/api/auth/dingtalk-bind/start$", "account.dingtalk_bind"),
    _rule("POST", r"^/api/auth/oauth/dingtalk/bind/complete$", "account.dingtalk_bind"),
    _rule("POST", r"^/api/auth/dingtalk-bind/unbind(?:/start)?$", "account.dingtalk_unbind"),
    _rule("DELETE", r"^/api/auth/oauth/links/[^/]+$", "account.oauth_unlink"),
    _rule("DELETE", r"^/api/diagrams/[^/]+$", "diagram.delete"),
    _rule("PUT", r"^/api/diagrams/[^/]+/shares$", "diagram.share"),
    _rule("POST", r"^/api/diagrams/[^/]+/workshop/start$", "workshop.start"),
    _rule("POST", r"^/api/diagrams/[^/]+/workshop/stop$", "workshop.stop"),
    _rule("POST", r"^/api/mindmate/seminar/start$", "seminar.start"),
    _rule("POST", r"^/api/mindmate/seminar/stop$", "seminar.stop"),
    _rule("POST", r"^/api/mindmate/seminar/members$", "seminar.member_add"),
    _rule("DELETE", r"^/api/mindmate/seminar/members$", "seminar.member_remove"),
    _rule("PATCH", r"^/api/mindmate/seminar/members/role$", "seminar.member_role"),
    _rule("POST", r"^/api/chat/channels$", "chat.channel_create"),
    _rule("POST", r"^/api/chat/channels/[^/]+/duplicate$", "chat.channel_create"),
    _rule("DELETE", r"^/api/chat/channels/[^/]+/permanent$", "chat.channel_delete"),
    _rule("DELETE", r"^/api/chat/channels/[^/]+$", "chat.channel_delete"),
    _rule("POST", r"^/api/chat/channels/[^/]+/invite$", "chat.channel_invite"),
    _rule("PATCH", r"^/api/chat/channels/[^/]+/permissions$", "chat.channel_permissions"),
    _rule("POST", r"^/api/showcase/posts$", "showcase.submit"),
    _rule("POST", r"^/api/showcase/posts/[^/]+/withdraw$", "showcase.withdraw"),
    _rule("POST", r"^/api/showcase/posts/[^/]+/delist$", "showcase.delist"),
    _rule("DELETE", r"^/api/showcase/posts/[^/]+$", "showcase.delete"),
    _rule("POST", r"^/api/showcase/posts/[^/]+/delete$", "showcase.delete"),
    _rule("POST", r"^/api/knowledge-space/documents/(?:batch-)?upload$", "knowledge.upload"),
    _rule(
        "POST",
        r"^/api/knowledge-space/packages/[^/]+/documents/(?:upload|ingest-text|ingest-web|ingest-web-url)$",
        "knowledge.upload",
    ),
    _rule("DELETE", r"^/api/knowledge-space/documents/[^/]+$", "knowledge.delete"),
    _rule("DELETE", r"^/api/doc-summary/documents/[^/]+$", "knowledge.delete"),
    _rule("POST", r"^/api/knowledge-space/packages$", "knowledge.package_create"),
    _rule("DELETE", r"^/api/knowledge-space/packages/[^/]+$", "knowledge.package_delete"),
    _rule("DELETE", r"^/api/doc-summary/packages/[^/]+$", "knowledge.package_delete"),
    _rule("PUT", r"^/api/knowledge-space/settings$", "knowledge.settings"),
    _rule("POST", r"^/api/knowledge-space/chat-handoff/ingest$", "knowledge.ingest"),
    _rule("POST", r"^/api/training/courses$", "course.create"),
    _rule("DELETE", r"^/api/training/courses/[^/]+$", "course.delete"),
    _rule(
        "POST",
        r"^/api/learning-space/teacher/students/[^/]+/reset-password$",
        "learning_space.teacher_password_reset",
    ),
    _rule("POST", r"^/api/learning-space/teacher/assignments$", "learning_space.assignment_create"),
    _rule("DELETE", r"^/api/learning-space/teacher/assignments/[^/]+$", "learning_space.assignment_delete"),
    _rule("POST", r"^/api/learning-space/teacher/assignments/[^/]+/delete$", "learning_space.assignment_delete"),
    _rule("POST", r"^/api/markets/orders$", "billing.order"),
    _rule("POST", r"^/api/markets/orders/[^/]+/pay$", "billing.pay"),
    _rule("POST", r"^/api/markets/subscriptions/intent$", "billing.subscribe"),
    _rule("POST", r"^/api/markets/subscriptions/[^/]+/cancel$", "billing.cancel"),
)


def classify_member_activity(method: str, path: str) -> Optional[str]:
    """Return an action key for an important non-admin write, or None."""
    if method not in _MUTATING:
        return None
    normalized = normalize_activity_path(path)
    for methods, pattern, action in _RULES:
        if method in methods and pattern.match(normalized):
            return action
    return None


def known_member_activity_actions() -> frozenset[str]:
    """Every member action the catalog can emit."""
    return frozenset(action for _methods, _pattern, action in _RULES)
