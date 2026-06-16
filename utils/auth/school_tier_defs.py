"""School tier slugs, limits table, and pure helpers (no org subscription or DB)."""

from __future__ import annotations

from typing import Final

from models.domain.messages import Language, Messages

SCHOOL_TIER_TRIAL: Final[str] = "trial"
SCHOOL_TIER_LITE: Final[str] = "lite"
SCHOOL_TIER_STANDARD: Final[str] = "standard"
SCHOOL_TIER_PROFESSIONAL: Final[str] = "professional"

SCHOOL_TIERS: Final[tuple[str, ...]] = (
    SCHOOL_TIER_TRIAL,
    SCHOOL_TIER_LITE,
    SCHOOL_TIER_STANDARD,
    SCHOOL_TIER_PROFESSIONAL,
)

DEFAULT_SCHOOL_TIER: Final[str] = SCHOOL_TIER_TRIAL

# Zero member_limit means no cap (trial schools may have hundreds of teachers).
SCHOOL_TIER_MEMBER_LIMIT_UNLIMITED: Final[int] = 0
# Maximum bonus seats above tier base member cap (admin-assigned per org).
EXTRA_MEMBER_SEATS_MAX: Final[int] = 500
# Zero diagram cap means no per-user saved-diagram limit (paid / personal accounts).
SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED: Final[int] = 0

DIAGRAM_SAVE_LIMIT_ERROR_PREFIX: Final[str] = "diagram_limit_reached:"

_GIB = 1024**3

SCHOOL_TIER_LIMITS: Final[dict[str, dict[str, int]]] = {
    SCHOOL_TIER_TRIAL: {
        "member_limit": SCHOOL_TIER_MEMBER_LIMIT_UNLIMITED,
        "manager_limit": 0,
        "diagram_storage_bytes_per_member": 1 * _GIB,
        "diagrams_per_member": 20,
    },
    SCHOOL_TIER_LITE: {
        "member_limit": 50,
        "manager_limit": 1,
        "diagram_storage_bytes_per_member": 1 * _GIB,
    },
    SCHOOL_TIER_STANDARD: {
        "member_limit": 120,
        "manager_limit": 3,
        "diagram_storage_bytes_per_member": 2 * _GIB,
    },
    SCHOOL_TIER_PROFESSIONAL: {
        "member_limit": 200,
        "manager_limit": 5,
        "diagram_storage_bytes_per_member": 5 * _GIB,
    },
}


TIER_FEATURE_ONLINE_COLLAB: Final[str] = "online_collab"
TIER_FEATURE_CHROME_EXTENSION: Final[str] = "chrome_extension"
TIER_FEATURE_PRESENTATION_TOOLS: Final[str] = "presentation_tools"
TIER_FEATURE_API_TOKEN: Final[str] = "api_token"

_STANDARD_PLUS_FEATURES: Final[frozenset[str]] = frozenset(
    {
        TIER_FEATURE_ONLINE_COLLAB,
        TIER_FEATURE_CHROME_EXTENSION,
        TIER_FEATURE_PRESENTATION_TOOLS,
        TIER_FEATURE_API_TOKEN,
    }
)


def normalize_school_tier(value: object | None) -> str:
    """Return a canonical tier slug; unknown values fall back to trial."""
    token = str(value or "").strip().lower()
    if token in SCHOOL_TIER_LIMITS:
        return token
    return DEFAULT_SCHOOL_TIER


def school_tier_allows_feature(tier: str, feature: str) -> bool:
    """Trial and lite tiers block collab, presentation tools, Chrome extension, and API tokens."""
    if feature not in _STANDARD_PLUS_FEATURES:
        return True
    normalized = normalize_school_tier(tier)
    return normalized not in (SCHOOL_TIER_TRIAL, SCHOOL_TIER_LITE)


def school_tier_features_payload(tier: str) -> dict[str, bool]:
    """Feature flags derived from a school's tier slug."""
    normalized = normalize_school_tier(tier)
    allows_premium = normalized not in (SCHOOL_TIER_TRIAL, SCHOOL_TIER_LITE)
    return {
        TIER_FEATURE_ONLINE_COLLAB: allows_premium,
        TIER_FEATURE_CHROME_EXTENSION: allows_premium,
        TIER_FEATURE_PRESENTATION_TOOLS: allows_premium,
        TIER_FEATURE_API_TOKEN: allows_premium,
    }


def school_tier_features_for_no_org() -> dict[str, bool]:
    """Personal / non-org accounts keep premium canvas features enabled."""
    return school_tier_features_payload(SCHOOL_TIER_PROFESSIONAL)


def is_unlimited_member_limit(limit: int) -> bool:
    """True when the tier has no member cap (member_limit <= 0)."""
    return int(limit) <= 0


def is_unlimited_diagram_limit(limit: int) -> bool:
    """True when the user has no saved-diagram count cap (limit <= 0)."""
    return int(limit) <= 0


def is_manager_assignment_unavailable(limit: int) -> bool:
    """True when the tier does not allow school managers (manager_limit <= 0)."""
    return int(limit) <= 0


def format_diagram_save_limit_error(cap: int) -> str:
    """Machine-readable diagram quota error token for API routers to localize."""
    return f"{DIAGRAM_SAVE_LIMIT_ERROR_PREFIX}{int(cap)}"


def parse_diagram_save_limit_error(error: str | None) -> int | None:
    """Return the diagram cap from a quota error token, or None if not a limit error."""
    if not error or not error.startswith(DIAGRAM_SAVE_LIMIT_ERROR_PREFIX):
        return None
    token = error[len(DIAGRAM_SAVE_LIMIT_ERROR_PREFIX) :]
    try:
        return int(token)
    except ValueError:
        return None


def diagram_limit_reached_message(lang: Language, limit: int) -> str:
    """Localized message when a trial user hits the saved-diagram cap."""
    return Messages.error("diagram_limit_reached", lang, limit)


def diagram_storage_bytes_per_member_for_tier(tier: str) -> int:
    """Diagram storage allowance per member (bytes) for a tier slug."""
    normalized = normalize_school_tier(tier)
    return int(SCHOOL_TIER_LIMITS[normalized]["diagram_storage_bytes_per_member"])


def max_diagrams_for_tier(tier: str) -> int:
    """Saved-diagram cap for a school tier (0 = unlimited; trial = 20)."""
    limits = SCHOOL_TIER_LIMITS[normalize_school_tier(tier)]
    tier_cap = limits.get("diagrams_per_member")
    if tier_cap is not None:
        return int(tier_cap)
    return SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED
