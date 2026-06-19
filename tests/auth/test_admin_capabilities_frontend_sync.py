"""Backend ROLE_PANEL_CAPABILITIES must match frontend adminCapabilities.ts."""

from __future__ import annotations

import re
from pathlib import Path

from utils.auth.admin_panel_permissions import ROLE_PANEL_CAPABILITIES
from utils.auth.role_constants import ALL_USER_ROLES

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_CAPS = ROOT / "frontend" / "src" / "utils" / "adminCapabilities.ts"

ROLE_BLOCK = re.compile(
    r"export const ROLE_PANEL_CAPABILITIES: Record<UserRole, AdminCapability\[\]> = \{(.*?)\n\}",
    re.DOTALL,
)
ROLE_ENTRY = re.compile(r"(\w+):\s*(\w+|\[\])")


def _frontend_role_caps() -> dict[str, frozenset[str]]:
    text = FRONTEND_CAPS.read_text(encoding="utf-8")
    const_blocks = dict(re.findall(r"const (\w+): AdminCapability\[\] = \[(.*?)\]", text, re.DOTALL))
    block_match = ROLE_BLOCK.search(text)
    assert block_match is not None, "ROLE_PANEL_CAPABILITIES block missing in adminCapabilities.ts"
    mapping: dict[str, frozenset[str]] = {}
    for role, value in ROLE_ENTRY.findall(block_match.group(1)):
        if value == "[]":
            mapping[role] = frozenset()
            continue
        raw = const_blocks.get(value, "")
        caps = frozenset(re.findall(r"'([^']+)'", raw))
        mapping[role] = caps
    return mapping


def test_frontend_role_panel_capabilities_match_backend():
    """Every role map in TS mirrors Python ROLE_PANEL_CAPABILITIES."""
    frontend = _frontend_role_caps()
    assert set(frontend) == set(ALL_USER_ROLES)
    for role in ALL_USER_ROLES:
        backend = ROLE_PANEL_CAPABILITIES[role]
        assert frontend[role] == backend, f"capability mismatch for role {role}"
