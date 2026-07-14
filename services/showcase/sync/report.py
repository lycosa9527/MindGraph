"""Typed reports for Showcase COS ↔ DB reconciliation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ShowcaseStorageStatus:
    """Health snapshot for admin storage status endpoint."""

    backend: str
    cos_enabled: bool
    credentials_configured: bool
    bucket: str
    region: str
    prefix: str
    connection_ok: bool
    connection_detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize status for JSON responses."""
        return asdict(self)


@dataclass
class ShowcaseReconcileReport:
    """Diff between Postgres media keys and COS objects under the Showcase prefix."""

    backend: str
    db_key_count: int = 0
    cos_object_count: int = 0
    matched: list[str] = field(default_factory=list)
    orphan_cos: list[str] = field(default_factory=list)
    missing_in_cos: list[str] = field(default_factory=list)
    unscoped: list[str] = field(default_factory=list)
    legacy_local: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize report with count convenience fields."""
        data = asdict(self)
        data["matched_count"] = len(self.matched)
        data["orphan_cos_count"] = len(self.orphan_cos)
        data["missing_in_cos_count"] = len(self.missing_in_cos)
        data["unscoped_count"] = len(self.unscoped)
        data["legacy_local_count"] = len(self.legacy_local)
        return data


def diff_key_sets(
    *,
    db_logical_keys: set[str],
    cos_logical_keys: set[str],
    scoped_check,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Pure diff helper (unit-testable).

    Returns matched, orphan_cos, missing_in_cos, unscoped (sorted lists).
    """
    matched = sorted(db_logical_keys & cos_logical_keys)
    missing = sorted(db_logical_keys - cos_logical_keys)
    cos_only = cos_logical_keys - db_logical_keys
    orphan: list[str] = []
    unscoped: list[str] = []
    for key in sorted(cos_only):
        if scoped_check(key):
            orphan.append(key)
        else:
            unscoped.append(key)
    return matched, orphan, missing, unscoped
