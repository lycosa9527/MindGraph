"""Centralized multilingual message system for MindGraph API responses.

Bundles live in ``message_catalog/bundled_messages.py`` (large dict literals).
Tier-27 UI locale codes are filled at import from ``en`` (``zh-tw`` uses ``zh`` first).

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司
(Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Literal, Optional, cast

from models.domain.api_locale import API_MESSAGE_LOCALE_SET, resolve_request_language_header
from models.domain.message_catalog import bundled_messages
from models.domain.message_catalog.expand_locales import expand_message_bundle


Language = Literal[
    "zh-tw",
    "zh",
    "en",
    "es",
    "az",
    "th",
    "fr",
    "de",
    "sq",
    "ja",
    "ko",
    "pt",
    "ru",
    "ar",
    "fa",
    "uz",
    "nl",
    "it",
    "hi",
    "id",
    "tl",
    "vi",
    "tr",
    "pl",
    "uk",
    "ms",
    "af",
]

expand_message_bundle(bundled_messages.ERRORS)
expand_message_bundle(bundled_messages.SUCCESS)
expand_message_bundle(bundled_messages.WARNINGS)


class Messages:
    """Centralized multilingual message system"""

    ERRORS = bundled_messages.ERRORS
    SUCCESS = bundled_messages.SUCCESS
    WARNINGS = bundled_messages.WARNINGS

    @classmethod
    def get(cls, category: str, key: str, *args: object, lang: Language = "en") -> str:
        """
        Get a message in the specified language.

        Args:
            category: Message category ('ERRORS', 'SUCCESS', 'WARNINGS')
            key: Message key
            *args: Format arguments for messages with placeholders.
                   If the first positional arg equals a tier-27 locale code (historically ``zh``, ``en``,
                   ``az``), it is treated as lang and removed from formatting args for compatibility.
            lang: Requested API locale keyword (tier-27 code).

        Returns:
            Localized message string (falls back ``en``, then raw key).
        """
        format_args = list(args)
        if format_args and isinstance(format_args[0], str):
            potential_lang = format_args[0].lower().replace("_", "-")
            if potential_lang in API_MESSAGE_LOCALE_SET:
                lang = cast(Language, potential_lang)
                format_args = format_args[1:]

        messages = getattr(cls, category, {})
        message_dict = messages.get(key, {})
        resolved = message_dict.get(lang) or message_dict.get("en") or key
        message = resolved

        if format_args:
            try:
                return message.format(*format_args)
            except (IndexError, KeyError, ValueError):
                return message

        return message

    @classmethod
    def error(cls, key: str, *args: object, lang: Language = "en") -> str:
        """Get an error message"""
        return cls.get("ERRORS", key, *args, lang=lang)

    @classmethod
    def success(cls, key: str, *args: object, lang: Language = "en") -> str:
        """Get a success message"""
        return cls.get("SUCCESS", key, *args, lang=lang)

    @classmethod
    def warning(cls, key: str, *args: object, lang: Language = "en") -> str:
        """Get a warning message"""
        return cls.get("WARNINGS", key, *args, lang=lang)


def get_request_language(
    language_header: Optional[str] = None,
    accept_language: Optional[str] = None,
) -> Language:
    """Resolve ``X-Language`` / Accept-Language to a tier-27 locale (default ``en``)."""
    return cast(Language, resolve_request_language_header(language_header, accept_language))
