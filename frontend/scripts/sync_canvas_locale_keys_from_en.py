#!/usr/bin/env python3
"""Add missing canvas.ts keys from en into every other locale (English fallback values)."""

from __future__ import annotations

import re
from pathlib import Path

LOCALES_ROOT = Path(__file__).resolve().parents[1] / "src" / "locales" / "messages"
SOURCE = LOCALES_ROOT / "en" / "canvas.ts"

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


def _render_entries(entries: dict[str, str], key_order: list[str]) -> str:
    lines = ["export default {"]
    for key in key_order:
        body = entries[key]
        lines.append(f"  '{key}':{body},")
    lines.append("} as const")
    lines.append("")
    return "\n".join(lines)


def _read_header(text: str) -> str:
    idx = text.find("export default {")
    if idx <= 0:
        return "/** Canvas UI messages */\n\n"
    return text[:idx]


def main() -> None:
    """Merge missing canvas.ts keys from en into every other locale bundle."""
    source_text = SOURCE.read_text(encoding="utf-8")
    source_entries = _parse_entries(source_text)
    source_order = list(_parse_entries(source_text).keys())

    for locale_dir in sorted(LOCALES_ROOT.iterdir()):
        if not locale_dir.is_dir() or locale_dir.name == "en":
            continue
        target_path = locale_dir / "canvas.ts"
        if not target_path.exists():
            continue
        text = target_path.read_text(encoding="utf-8")
        header = _read_header(text)
        entries = _parse_entries(text)
        for key in source_order:
            if key not in entries:
                entries[key] = source_entries[key]
        key_order = list(_parse_entries(text).keys())
        for key in source_order:
            if key not in key_order:
                key_order.append(key)
        merged = {key: entries[key] for key in key_order if key in entries}
        target_path.write_text(header + _render_entries(merged, key_order), encoding="utf-8")
        print(f"synced {locale_dir.name}/canvas.ts")


if __name__ == "__main__":
    main()
