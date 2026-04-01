"""Compare each locale's message values to English (same keys as `en/`).

Run from repo root:
  python frontend/scripts/analyze_i18n_en_parity.py
  python frontend/scripts/analyze_i18n_en_parity.py --common-only

Interpretation:
- High % same as `en` means most user-visible strings are still English.
- Low % for `zh` / `zh-tw` is expected (Chinese, not English).
- Only single-quoted `'key': 'value'` pairs are counted (same limitation as materialize tooling).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent / "src" / "locales" / "messages"
en_root = root / "en"

pattern = re.compile(r"'([^']+)':\s*'((?:[^'\\]|\\.)*)'")


def parse_ts_strings(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    d: dict[str, str] = {}
    for m in pattern.finditer(text):
        key, val = m.group(1), m.group(2)
        val = val.replace("\\'", "'").replace("\\n", "\n")
        d[key] = val
    return d


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
    args = parser.parse_args()
    modules = ["common.ts"] if args.common_only else discover_modules()

    en_flat = load_flat("en", modules)
    en_keys = set(en_flat)
    if not en_keys:
        raise SystemExit("No keys parsed from en/ — check quote style in message files.")

    rows: list[tuple[str, float, int, int]] = []
    for loc in sorted(p.name for p in root.iterdir() if p.is_dir()):
        if loc == "en":
            continue
        loc_flat = load_flat(loc, modules)
        common = en_keys & set(loc_flat)
        if not common:
            rows.append((loc, 0.0, 0, len(en_keys)))
            continue
        same = sum(1 for k in common if loc_flat.get(k) == en_flat.get(k))
        pct = 100.0 * same / len(common)
        rows.append((loc, round(pct, 1), same, len(common)))

    rows.sort(key=lambda x: (-x[1], x[0]))
    scope = "common.ts" if args.common_only else "all modules (" + ", ".join(modules) + ")"
    print(f"scope\t{scope}")
    print(f"keys_in_en\t{len(en_keys)}")
    print("locale\tpct_same_as_en\tmatching\tkeys_compared")
    for r in rows:
        print(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}")


if __name__ == "__main__":
    main()
