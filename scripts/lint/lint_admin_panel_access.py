#!/usr/bin/env python3
"""Flag panel admin routes still using raw require_admin or inline is_admin()."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTERS = ROOT / "routers"

REQUIRE_ADMIN_DEP = re.compile(r"Depends\(\s*require_admin\s*\)")
INLINE_IS_ADMIN = re.compile(r"if\s+not\s+is_admin\(\s*current_user\s*\)|is_admin\(\s*current_user\s*\)")

# Product / legacy routes — not management-panel ACL (see admin access sweep plan).
SKIP_FILES = frozenset(
    {
        "routers/auth/dependencies.py",
        "routers/auth/quick_register.py",
        "routers/api/config.py",
        "routers/features/workshop_chat/channels.py",
        "routers/features/workshop_chat/dependencies.py",
        "routers/features/library/danmaku.py",
        "routers/features/community.py",
        "routers/api/canvas_translate.py",
    }
)

# users.py: global user mutations stay on require_admin (superadmin-only).
USERS_MUTATION_ALLOW = re.compile(
    r'@router\.(put|delete)\("/admin/users/\{user_id\}',
    re.IGNORECASE,
)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _line_no(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


def _in_users_mutation_block(text: str, match_start: int) -> bool:
    """True when match sits under an allowlisted users.py mutation route."""
    block_start = max(text.rfind("\n@router", 0, match_start), 0)
    block = text[block_start : match_start + 200]
    return bool(USERS_MUTATION_ALLOW.search(block))


def _scan_require_admin(path: Path, text: str) -> list[str]:
    rel = _rel(path)
    if rel in SKIP_FILES:
        return []
    violations: list[str] = []
    for match in REQUIRE_ADMIN_DEP.finditer(text):
        if rel == "routers/auth/admin/users.py" and _in_users_mutation_block(text, match.start()):
            continue
        line = _line_no(text, match.start())
        violations.append(f"{rel}:{line}: Depends(require_admin) — use require_panel_capability(CAP_*) helper")
    return violations


def _scan_inline_is_admin(path: Path, text: str) -> list[str]:
    rel = _rel(path)
    if rel in SKIP_FILES:
        return []
    violations: list[str] = []
    for match in INLINE_IS_ADMIN.finditer(text):
        line = _line_no(text, match.start())
        if (
            rel == "routers/auth/admin/stats.py"
            and "get_admin_status" in text[max(0, text.rfind("\n@", 0, match.start())) : match.start() + 80]
        ):
            continue
        violations.append(f"{rel}:{line}: inline is_admin(current_user) — use Depends(require_* cap helper)")
    return violations


def main() -> int:
    """Main."""
    violations: list[str] = []
    for path in sorted(ROUTERS.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        violations.extend(_scan_require_admin(path, text))
        violations.extend(_scan_inline_is_admin(path, text))
    if violations:
        print("Admin panel access lint violations:")
        for item in violations:
            print(f"  {item}")
        return 1
    print("Admin panel access lint: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
