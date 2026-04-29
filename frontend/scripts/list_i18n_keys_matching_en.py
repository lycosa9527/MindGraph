"""List keys whose translated value still equals English (translation backlog).

Run from repo root, e.g.:
  python frontend/scripts/list_i18n_keys_matching_en.py --locale ja --modules admin.ts,canvas.ts
  python frontend/scripts/list_i18n_keys_matching_en.py --locale es --max 40
"""

from __future__ import annotations

import argparse

from analyze_i18n_en_parity import discover_modules, load_flat


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print keys where locale value equals en (same string).",
    )
    parser.add_argument("--locale", required=True, help="Locale folder name, e.g. ja")
    parser.add_argument(
        "--modules",
        type=str,
        default="",
        help="Comma-separated modules (default: all en/ modules except index.ts)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="Max keys to print (0 = no limit)",
    )
    args = parser.parse_args()
    loc = args.locale.strip()
    if not loc or loc == "en":
        raise SystemExit("--locale must be a non-en locale code")

    modules = discover_modules()
    if args.modules.strip():
        modules = [m.strip() for m in args.modules.split(",") if m.strip()]

    en_flat = load_flat("en", modules)
    loc_flat = load_flat(loc, modules)
    common_keys = sorted(set(en_flat) & set(loc_flat))
    matches = [k for k in common_keys if loc_flat[k] == en_flat[k]]
    print(f"locale\t{loc}")
    print(f"modules\t{', '.join(modules)}")
    print(f"keys_same_as_en\t{len(matches)}")
    print(f"keys_compared\t{len(common_keys)}")
    out = matches if args.max <= 0 else matches[: args.max]
    for key in out:
        print(key)


if __name__ == "__main__":
    main()
