#!/usr/bin/env python3
"""Sync DingTalk pair-code locale keys from en to other locales (except zh)."""

from __future__ import annotations

import re
from pathlib import Path

LOCALES_ROOT = Path(__file__).resolve().parents[1] / "src" / "locales" / "messages"
SOURCE = LOCALES_ROOT / "en" / "auth.ts"
SKIP_LOCALES = frozenset({"en", "zh"})

KEYS = (
    "auth.dingtalkBindInstructions",
    "auth.dingtalkBindPairWaiting",
    "auth.dingtalkBindCodeHint",
    "auth.dingtalkBindCountdown",
    "auth.dingtalkBindCodeRefreshIn",
    "auth.dingtalkBindExpiredHint",
    "auth.dingtalkBindRegenerate",
    "auth.dingtalkUnbindTitle",
    "auth.dingtalkUnbindInstructions",
    "auth.dingtalkUnbindPairWaiting",
    "auth.dingtalkUnbindCodeHint",
    "auth.dingtalkUnbindExpiredHint",
    "auth.dingtalkUnbindRegenerate",
    "auth.dingtalkUnbindNotLinked",
)

OBSOLETE_KEYS = (
    "auth.dingtalkBindQrAlt",
    "auth.dingtalkBindQrRefreshIn",
    "auth.dingtalkBindQrHint",
)

ENTRY_RE = re.compile(
    r"(?P<prefix>\n  )'(?P<key>[^']+)':(?P<body>.*?)(?=\n  '|\n} as const)",
    re.DOTALL,
)


def _strip_entry_trailing_commas(body: str) -> str:
    return re.sub(r",+\s*$", "", body)


def _parse_entries(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for match in ENTRY_RE.finditer(text):
        entries[match.group("key")] = _strip_entry_trailing_commas(match.group("body"))
    return entries


def _render_entry(key: str, body: str) -> str:
    return f"  '{key}':{_strip_entry_trailing_commas(body)}"


def main() -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    source_entries = _parse_entries(source_text)
    missing = [key for key in KEYS if key not in source_entries]
    if missing:
        raise SystemExit(f"Missing keys in en/auth.ts: {missing}")

    for locale_dir in sorted(LOCALES_ROOT.iterdir()):
        if not locale_dir.is_dir() or locale_dir.name in SKIP_LOCALES:
            continue
        target_path = locale_dir / "auth.ts"
        if not target_path.exists():
            continue
        text = target_path.read_text(encoding="utf-8")
        entries = _parse_entries(text)
        for obsolete in OBSOLETE_KEYS:
            entries.pop(obsolete, None)
        for key in KEYS:
            entries[key] = source_entries[key]
        ordered_keys = list(_parse_entries(text).keys())
        for key in KEYS:
            if key not in ordered_keys:
                ordered_keys.append(key)
        ordered_keys = [key for key in ordered_keys if key not in OBSOLETE_KEYS]
        rebuilt = "export default {\n"
        for key in ordered_keys:
            if key not in entries:
                continue
            rebuilt += _render_entry(key, entries[key]) + ",\n"
        rebuilt += "} as const\n"
        target_path.write_text(rebuilt, encoding="utf-8")
        print(f"updated {target_path.relative_to(LOCALES_ROOT.parents[1])}")


if __name__ == "__main__":
    main()
