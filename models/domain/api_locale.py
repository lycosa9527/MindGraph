"""API response locale codes aligned with SPA tier-27 interface (``X-Language``).

These codes match ``INTERFACE_LANGUAGE_PICKER_CODES`` in ``frontend/src/i18n/locales.ts``.
"""
from __future__ import annotations

from typing import Final, Optional

# Must stay in sync with frontend INTERFACE_LANGUAGE_PICKER_CODES / tier-27 list.
API_MESSAGE_LOCALE_CODES: Final[tuple[str, ...]] = (
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
)

API_MESSAGE_LOCALE_SET: Final[frozenset[str]] = frozenset(API_MESSAGE_LOCALE_CODES)

_ALIASES: Final[dict[str, str]] = {
    "zht": "zh-tw",
    "zh-hk": "zh-tw",
    "zh-hant": "zh-tw",
    "zh_cn": "zh",
    "chs": "zh",
    "chs-cn": "zh",
    "zh-hans": "zh",
    "zh-cn": "zh",
    "zh-sg": "zh",
    "chinese": "zh",
    "en-us": "en",
    "en-gb": "en",
    "pt-br": "pt",
}


def _normalize_header_value(raw: str) -> str:
    part = raw.split(",")[0].split(";")[0].strip().strip('"')
    return part.lower().replace("_", "-")


def resolve_request_locale(language_header: Optional[str]) -> Optional[str]:
    """Map an X-Language / browser tag to a canonical tier-27 code, or None."""
    if not language_header:
        return None
    lowered = _normalize_header_value(language_header)

    lowered = _ALIASES.get(lowered, lowered)

    if lowered in API_MESSAGE_LOCALE_SET:
        return lowered

    if "-" in lowered:
        primary = lowered.split("-", maxsplit=1)[0]
        if primary in API_MESSAGE_LOCALE_SET:
            return primary

    if lowered.startswith("zh"):
        if (
            "tw" in lowered
            or lowered.endswith("-hk")
            or "hant" in lowered
            or lowered == "zht"
        ):
            return "zh-tw"
        return "zh"

    return None


def resolve_accept_language(accept_language: Optional[str]) -> Optional[str]:
    """Best-effort: first tag only."""
    if not accept_language:
        return None
    return resolve_request_locale(accept_language)


def resolve_request_language_header(
    language_header: Optional[str] = None,
    accept_language: Optional[str] = None,
) -> str:
    """Return a tier-27 API locale or English as default."""
    resolved = resolve_request_locale(language_header) if language_header else None
    if resolved:
        return resolved
    resolved_accept = resolve_accept_language(accept_language)
    if resolved_accept:
        return resolved_accept
    return "en"
