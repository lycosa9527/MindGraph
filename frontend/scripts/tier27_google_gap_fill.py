"""Run Google gap-fill batch for Tier-27 picker locales (flat modules + canvas).

Requires VPN if Google Translate is blocked. Review output before release.

Usage (repo root):
  python frontend/scripts/tier27_google_gap_fill.py --phase a
  python frontend/scripts/tier27_google_gap_fill.py --phase b
  python frontend/scripts/tier27_google_gap_fill.py --phase all
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent.parent
_PY = sys.executable

_LOCALES_TS = _SCRIPTS.parent / "src/i18n/locales.ts"

PHASE_A_FLAT = ("notification.ts", "sidebar.ts", "common.ts")
PHASE_B_FLAT = (
    "admin.ts",
    "auth.ts",
    "community.ts",
    "knowledge.ts",
    "mindmate.ts",
    "workshop.ts",
)


def _picker_non_en_ordered() -> list[str]:
    text = _LOCALES_TS.read_text(encoding="utf-8")
    marker = "INTERFACE_LANGUAGE_PICKER_CODES"
    idx = text.index(marker)
    sub = text[idx:]
    open_br = sub.index("[")
    tail = sub[open_br:]
    end_marker = "] as const"
    close_rel = tail.index(end_marker)
    block = tail[: close_rel + 1]
    codes = re.findall(r"'([^']+)'", block)
    if not codes:
        raise SystemExit(f"No picker codes parsed from {_LOCALES_TS}")
    return [c for c in codes if c != "en"]


def _run(script_name: str, args: list[str]) -> int:
    cmd = [_PY, str(_SCRIPTS / script_name), *args]
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(_REPO), check=False)
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tier-27 Google gap-fill for picker locales.")
    parser.add_argument(
        "--phase",
        choices=("a", "b", "all"),
        default="all",
        help="Phase A = notification/sidebar/common + canvas; Phase B = remaining modules.",
    )
    parser.add_argument(
        "--start-from",
        default="",
        help="Skip locales until this code (e.g. id) in picker order; then run rest.",
    )
    args = parser.parse_args()

    locales = _picker_non_en_ordered()
    if args.start_from.strip():
        marker = args.start_from.strip()
        if marker not in locales:
            raise SystemExit(f"--start-from {marker!r} not in picker list")
        locales = locales[locales.index(marker) :]

    if args.phase in ("a", "all"):
        for loc in locales:
            for mod in PHASE_A_FLAT:
                code = _run(
                    "batch_translate_flat_module_google.py",
                    [loc, mod],
                )
                if code != 0:
                    return code
            code = _run("batch_translate_canvas_google.py", [loc])
            if code != 0:
                return code

    if args.phase in ("b", "all"):
        for loc in locales:
            for mod in PHASE_B_FLAT:
                code = _run(
                    "batch_translate_flat_module_google.py",
                    [loc, mod],
                )
                if code != 0:
                    return code

    print("tier27_google_gap_fill: done.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
