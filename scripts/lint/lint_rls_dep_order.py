#!/usr/bin/env python3
"""Flag FastAPI handlers that open get_async_db before AdminScope / panel auth deps."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTERS = ROOT / "routers"

DB_LINE = re.compile(
    r"^\s*db:\s*AsyncSession\s*=\s*Depends\(\s*get_async_db\s*\)\s*,?\s*$",
    re.MULTILINE,
)
DB_WITH_RLS = re.compile(
    r"Depends\(\s*get_async_db_with_request_rls\s*\)",
)
SCOPE_AFTER_DB = re.compile(
    r"^\s*(?:_\w+|scope):\s*AdminScope\s*=\s*Depends\(",
    re.MULTILINE,
)
PANEL_AUTH_AFTER_DB = re.compile(
    r"^\s*(?:user|current_user|_current_user):\s*User\s*=\s*Depends\(\s*"
    r"(?:require_admin|require_mindbot_admin_access)\s*\)\s*,?\s*$",
    re.MULTILINE,
)
ROUTE_ADMIN_DEP = re.compile(
    r"dependencies\s*=\s*\[\s*Depends\(\s*require_admin\s*\)\s*\]",
)


def _scan_file(path: Path) -> list[str]:
    """Scan file."""
    text = path.read_text(encoding="utf-8")
    violations: list[str] = []
    for match in DB_LINE.finditer(text):
        if DB_WITH_RLS.search(text[match.start() : match.end() + 400]):
            continue
        sig_end = text.find("\n):", match.end())
        if sig_end < 0 or sig_end > match.end() + 400:
            sig_end = match.end() + 400
        window = text[match.end() : sig_end]
        handler_start = text.rfind("\n@router", 0, match.start())
        if handler_start < 0:
            handler_start = text.rfind("\nasync def ", 0, match.start())
        if handler_start < 0:
            handler_start = text.rfind("\ndef ", 0, match.start())
        handler_chunk = text[handler_start : match.end()]
        if ROUTE_ADMIN_DEP.search(handler_chunk):
            continue
        line_no = text[: match.start()].count("\n") + 1
        if SCOPE_AFTER_DB.search(window):
            rel = path.relative_to(ROOT)
            violations.append(
                f"{rel}:{line_no}: db before AdminScope — use scope first or get_async_db_with_request_rls"
            )
            continue
        if PANEL_AUTH_AFTER_DB.search(window):
            rel = path.relative_to(ROOT)
            violations.append(
                f"{rel}:{line_no}: db before require_admin — put auth first or get_async_db_with_request_rls"
            )
    return violations


def main() -> int:
    """Main."""
    violations: list[str] = []
    for path in sorted(ROUTERS.rglob("*.py")):
        violations.extend(_scan_file(path))
    if violations:
        print("RLS dependency-order lint violations:")
        for item in violations:
            print(f"  {item}")
        return 1
    print("RLS dependency-order lint: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
