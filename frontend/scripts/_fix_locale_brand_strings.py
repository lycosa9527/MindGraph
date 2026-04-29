"""Set canonical ASCII brand strings for MindGraph / MindMate in locale TS files."""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "src", "locales", "messages")
)

PATCH_COMMON = {
    "meta.pageTitle.mindgraph": "MindGraph",
    "meta.pageTitle.mindmate": "MindMate",
    "landing.international.mindmateCard.title": "MindMate",
}

PATCH_SIDEBAR = {
    "sidebar.mindGraph": "MindGraph",
    "sidebar.mindMate": "MindMate",
}

PATCH_COMMUNITY = {
    "community.type.mindgraph": "MindGraph",
    "community.type.mindmate": "MindMate",
}


def patch_key_line(content: str, key: str, value: str) -> tuple[str, bool]:
    """Replace exported string value for a single-quote TS key."""
    pat = re.compile(rf"('{re.escape(key)}'\s*:\s*)'([^']*)'")

    def repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}'{value}'"

    new_content, count = pat.subn(repl, content, count=1)
    return new_content, count == 1


def main() -> int:
    touched = []

    def run_all(name: str, mapping: dict[str, str]) -> None:
        for locale in sorted(os.listdir(ROOT)):
            path = os.path.join(ROOT, locale, name)
            if not os.path.isfile(path):
                continue
            full = path
            rel = os.path.join("messages", locale, name)
            with open(full, encoding="utf-8") as handle:
                text = handle.read()
            buf = text
            for key, val in mapping.items():
                new_buf, replaced = patch_key_line(buf, key, val)
                if replaced:
                    buf = new_buf
            if buf != text:
                with open(full, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(buf)
                touched.append(rel)

    run_all("common.ts", PATCH_COMMON)
    run_all("sidebar.ts", PATCH_SIDEBAR)
    run_all("community.ts", PATCH_COMMUNITY)

    print(f"updated {len(touched)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
