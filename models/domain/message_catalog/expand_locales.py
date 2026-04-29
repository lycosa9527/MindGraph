"""Populate missing per-locale strings from English (zh for zh-tw) for API catalogs.

Authoring backlog: each message in ``bundled_messages.py`` may only define ``zh`` / ``en`` / ``az``.
``expand_message_bundle`` fills other ``API_MESSAGE_LOCALE_CODES`` from ``en``. Native copy for
those codes is added by extending the per-key dicts in ``bundled_messages.py`` (generated source),
not by changing this expander alone.
"""
from __future__ import annotations

from models.domain.api_locale import API_MESSAGE_LOCALE_CODES


def expand_message_bundle(category: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Ensure every inner dict has entries for tier-27 locale codes."""

    for _msg_key, variants in category.items():
        for code in API_MESSAGE_LOCALE_CODES:
            existing = variants.get(code)
            if existing:
                continue
            if code == "zh-tw":
                variants[code] = variants.get("zh") or variants.get("en") or ""
                continue
            variants[code] = variants.get("en") or ""
    return category
