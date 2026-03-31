"""
Verify frontend prompt registry JSON matches utils/prompt_output_languages.py.

Run from repository root, e.g.:
  python scripts/check_prompt_output_languages_sync.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _json_codes() -> list[str]:
    path = _REPO_ROOT / "data" / "prompt_language_registry.json"
    if not path.is_file():
        print(f"Missing {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as handle:
        rows = json.load(handle)
    return sorted(str(r["code"]).lower().strip() for r in rows)


def _typescript_codes() -> list[str]:
    path = _REPO_ROOT / "frontend" / "src" / "i18n" / "locales.ts"
    text = path.read_text(encoding="utf-8")
    if "prompt_language_registry.json" in text:
        return _json_codes()
    match = re.search(
        r"export const PROMPT_OUTPUT_LANGUAGE_CODES = \[([\s\S]*?)\] as const",
        text,
    )
    if not match:
        print("Could not find PROMPT_OUTPUT_LANGUAGE_CODES in locales.ts", file=sys.stderr)
        sys.exit(1)
    body = match.group(1)
    found = re.findall(r"'([^']+)'", body)
    return sorted(found)


def _python_codes() -> list[str]:
    mod_path = _REPO_ROOT / "utils" / "prompt_output_languages.py"
    spec = importlib.util.spec_from_file_location("prompt_output_languages", mod_path)
    if spec is None or spec.loader is None:
        print("Could not load prompt_output_languages.py", file=sys.stderr)
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    codes = getattr(module, "PROMPT_OUTPUT_LANGUAGE_CODES", None)
    if codes is None:
        print("PROMPT_OUTPUT_LANGUAGE_CODES missing", file=sys.stderr)
        sys.exit(1)
    return sorted(codes)


def main() -> None:
    """Compare JSON, TypeScript-derived list, and Python frozenset."""
    json_list = _json_codes()
    ts_list = _typescript_codes()
    py_list = _python_codes()
    if json_list != py_list:
        js = set(json_list)
        ps = set(py_list)
        print(
            "JSON vs Python mismatch:",
            {"only_in_json": sorted(js - ps), "only_in_py": sorted(ps - js)},
            file=sys.stderr,
        )
        sys.exit(1)
    if ts_list != py_list:
        ts_set = set(ts_list)
        py_set = set(py_list)
        print(
            "TypeScript vs Python mismatch:",
            {
                "only_in_ts": sorted(ts_set - py_set),
                "only_in_py": sorted(py_set - ts_set),
            },
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"OK: prompt output language codes match ({len(py_list)} entries).")


if __name__ == "__main__":
    main()
