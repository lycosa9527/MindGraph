"""Verify canonical MindGraph/MindMate in locale keys (development aid)."""

import os
import re
import sys

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "src", "locales", "messages")
)

PATTERNS = [
    ("common.ts", r"'meta\.pageTitle\.mindgraph': '([^']*)'", "MindGraph"),
    ("common.ts", r"'meta\.pageTitle\.mindmate': '([^']*)'", "MindMate"),
    (
        "common.ts",
        r"'landing\.international\.mindmateCard\.title': '([^']*)'",
        "MindMate",
    ),
    ("sidebar.ts", r"'sidebar\.mindGraph': '([^']*)'", "MindGraph"),
    ("sidebar.ts", r"'sidebar\.mindMate': '([^']*)'", "MindMate"),
    ("community.ts", r"'community\.type\.mindgraph': '([^']*)'", "MindGraph"),
    ("community.ts", r"'community\.type\.mindmate': '([^']*)'", "MindMate"),
]


def main() -> int:
    bad = []
    locale_dirs = sorted(d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, d)))
    for loc in locale_dirs:
        for fname, pattern, expected in PATTERNS:
            path = os.path.join(ROOT, loc, fname)
            if not os.path.isfile(path):
                continue
            text = open(path, encoding="utf-8").read()
            m = re.search(pattern, text)
            if not m:
                continue
            got = m.group(1)
            if got != expected:
                bad.append((loc, fname, pattern, got, expected))
    out = sys.stdout
    if bad:
        for row in bad:
            out.write(repr(row) + "\n")
        return 1
    out.write("OK: brand keys match across locales.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
