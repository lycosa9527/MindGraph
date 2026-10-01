"""Verify MindMate / MindGraph stay Latin wherever the Chinese catalog uses them."""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "src", "locales", "messages")
)
BRANDS = ("MindGraph", "MindMate")
ENTRY_RE = re.compile(
    r"'(?P<key>(?:\\'|[^'])*)'\s*:\s*"
    r"(?P<quote>['\"])(?P<val>(?:\\.|(?!(?P=quote)).)*)(?P=quote)"
)


def unescape(value: str) -> str:
    return value.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")


def load_entries(path: str) -> dict[str, str]:
    text = open(path, encoding="utf-8").read()
    return {match.group("key"): unescape(match.group("val")) for match in ENTRY_RE.finditer(text)}


def main() -> int:
    zh: dict[str, str] = {}
    zh_dir = os.path.join(ROOT, "zh")
    for name in os.listdir(zh_dir):
        if name.endswith(".ts"):
            zh.update(load_entries(os.path.join(zh_dir, name)))

    bad: list[str] = []
    for locale in sorted(os.listdir(ROOT)):
        locale_dir = os.path.join(ROOT, locale)
        if not os.path.isdir(locale_dir) or locale in ("zh", "__test__"):
            continue
        for name in os.listdir(locale_dir):
            if not name.endswith(".ts"):
                continue
            entries = load_entries(os.path.join(locale_dir, name))
            for key, value in entries.items():
                source = zh.get(key)
                if not source:
                    continue
                for brand in BRANDS:
                    if brand in source and brand not in value:
                        bad.append(f"{locale}/{name} {key} missing {brand}: {value[:80]!r}")
    if bad:
        sys.stdout.write(f"{len(bad)} brand strings drifted\n")
        sys.stdout.write("\n".join(bad[:40]) + "\n")
        return 1
    sys.stdout.write("OK: MindMate and MindGraph stay untranslated.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
