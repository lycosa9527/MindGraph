"""Header edition subtitle — mirrors frontend useAppSidebar brandSubtitleKind."""

from __future__ import annotations

from typing import Optional

from file_reader.api_client import OrganizationProfile, UserProfile
from file_reader.i18n import I18n

_PAID_SCHOOL_TIERS = frozenset({"lite", "standard", "professional"})
_ORG_NAME_MAX_LEN = 7


def _truncate_org_label(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        return ""
    return stripped[:_ORG_NAME_MAX_LEN]


def edition_subtitle_for_profile(i18n: I18n, profile: Optional[UserProfile]) -> str:
    """Return the second header line for the signed-in user, matching the web sidebar."""
    if profile is None:
        return i18n.translate("header.subtitle.guest")

    org: Optional[OrganizationProfile] = profile.organization
    org_id = org.id if org is not None else None
    school_tier = org.school_tier if org is not None else None
    school_name = ""
    if org is not None:
        school_name = (org.display_name or org.name or "").strip()

    if org_id and school_name and school_tier in _PAID_SCHOOL_TIERS:
        label = _truncate_org_label(school_name)
        return i18n.translate("header.subtitle.org_edition", org=label)

    if not org_id:
        return i18n.translate("header.subtitle.personal_edition")

    return ""
