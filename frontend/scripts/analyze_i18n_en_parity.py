"""Compare each locale's message values to English (same keys as `en/`).

Run from repo root:
  python frontend/scripts/analyze_i18n_en_parity.py
  python frontend/scripts/analyze_i18n_en_parity.py --common-only
  python frontend/scripts/analyze_i18n_en_parity.py --picker-only
  python frontend/scripts/analyze_i18n_en_parity.py --modules admin.ts,canvas.ts --picker-only

Interpretation:
- High % same as `en` means most user-visible strings are still English.
- Low % for `zh` / `zh-tw` is expected (Chinese, not English).
- Both single-quoted `'key': 'value'` and double-quoted `"key": "value"` pairs are counted.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent / "src" / "locales" / "messages"
en_root = root / "en"
locales_ts = Path(__file__).resolve().parent.parent / "src" / "i18n" / "locales.ts"

pattern_single = re.compile(r"'([^']+)':\s*'((?:[^'\\]|\\.)*)'")
pattern_double = re.compile(r'"([^"]+)":\s*"((?:[^"\\]|\\.)*)"')


def _unescape_single_quoted(val: str) -> str:
    return val.replace("\\'", "'").replace("\\n", "\n")


def _unescape_double_quoted(val: str) -> str:
    parts: list[str] = []
    idx = 0
    limit = len(val)
    while idx < limit:
        ch = val[idx]
        if ch == "\\" and idx + 1 < limit:
            nxt = val[idx + 1]
            if nxt == '"':
                parts.append('"')
                idx += 2
                continue
            if nxt == "\\":
                parts.append("\\")
                idx += 2
                continue
            if nxt == "n":
                parts.append("\n")
                idx += 2
                continue
            if nxt == "t":
                parts.append("\t")
                idx += 2
                continue
            parts.append("\\")
            idx += 1
            continue
        parts.append(ch)
        idx += 1
    return "".join(parts)


def parse_ts_strings(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    merged: dict[str, str] = {}
    for m in pattern_single.finditer(text):
        key, val = m.group(1), m.group(2)
        merged[key] = _unescape_single_quoted(val)
    for m in pattern_double.finditer(text):
        key, val = m.group(1), m.group(2)
        merged[key] = _unescape_double_quoted(val)
    return merged


def load_interface_picker_codes() -> frozenset[str]:
    text = locales_ts.read_text(encoding="utf-8")
    marker = "INTERFACE_LANGUAGE_PICKER_CODES"
    idx = text.index(marker)
    sub = text[idx:]
    open_br = sub.index("[")
    tail = sub[open_br:]
    end_marker = "] as const"
    close_rel = tail.index(end_marker)
    block = tail[: close_rel + 1]
    codes = frozenset(re.findall(r"'([^']+)'", block))
    if not codes:
        raise RuntimeError(f"No picker codes parsed from {locales_ts}")
    return codes


def discover_modules() -> list[str]:
    return sorted(
        p.name for p in en_root.iterdir() if p.suffix == ".ts" and p.name != "index.ts"
    )


def load_flat(loc: str, modules: list[str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for mod in modules:
        path = root / loc / mod
        if not path.is_file():
            continue
        merged.update(parse_ts_strings(path))
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare locale strings to en.")
    parser.add_argument(
        "--common-only",
        action="store_true",
        help="Only scan common.ts (faster)",
    )
    parser.add_argument(
        "--picker-only",
        action="store_true",
        help="Only list locales in INTERFACE_LANGUAGE_PICKER_CODES (excluding en)",
    )
    parser.add_argument(
        "--modules",
        type=str,
        default="",
        help="Comma-separated module filenames (default: all non-index .ts under en/)",
    )
    args = parser.parse_args()
    if args.common_only:
        modules = ["common.ts"]
    else:
        modules = discover_modules()
        if args.modules.strip():
            modules = [m.strip() for m in args.modules.split(",") if m.strip()]

    en_flat = load_flat("en", modules)
    en_keys = set(en_flat)
    if not en_keys:
        raise SystemExit("No keys parsed from en/ — check quote style in message files.")

    picker_codes = load_interface_picker_codes() if args.picker_only else None

    rows: list[tuple[str, float, int, int]] = []
    for loc in sorted(p.name for p in root.iterdir() if p.is_dir()):
        if loc == "en":
            continue
        if picker_codes is not None and loc not in picker_codes:
            continue
        loc_flat = load_flat(loc, modules)
        common = en_keys & set(loc_flat)
        if not common:
            rows.append((loc, 0.0, 0, len(en_keys)))
            continue
        same_count = sum(1 for key in common if loc_flat.get(key) == en_flat.get(key))
        pct = 100.0 * same_count / len(common)
        rows.append((loc, round(pct, 1), same_count, len(common)))

    rows.sort(key=lambda row: (-row[1], row[0]))
    scope_bits = []
    if args.common_only:
        scope_bits.append("common.ts")
    elif args.modules.strip():
        scope_bits.append("modules=" + ",".join(modules))
    else:
        scope_bits.append("all modules (" + ", ".join(modules) + ")")
    if args.picker_only:
        scope_bits.append("picker tier-27 only")
    print(f"scope\t{'; '.join(scope_bits)}")
    print(f"keys_in_en\t{len(en_keys)}")
    print("locale\tpct_same_as_en\tmatching\tkeys_compared")
    for row in rows:
        print(f"{row[0]}\t{row[1]}\t{row[2]}\t{row[3]}")


if __name__ == "__main__":
    main()
