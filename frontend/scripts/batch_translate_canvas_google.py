"""Batch-translate `canvas.ts` values EN→locale via Google (deep_translator).

Uses the unofficial translate endpoint; keep VPN/firewall access in mind.
Scaffolding only — review strings (brands, math, tone) before shipping.

Preserves `{placeholder}` segments. Key order and multiline layout follow
`nl/canvas.ts` (same contract as other Tier-27 canvas emitters).

Examples (from repo root):
  python frontend/scripts/batch_translate_canvas_google.py sq --max 5
  python frontend/scripts/batch_translate_canvas_google.py ar --delay 0.5
  python frontend/scripts/batch_translate_canvas_google.py hi --force-all
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

import requests
from deep_translator import GoogleTranslator
from deep_translator.exceptions import RequestError, TooManyRequests

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _i18n_google_batch_shared import (
    google_target,
    patch_requests_timeout,
    shield_placeholders,
    translate_with_retries,
    unshield_placeholders,
)
from batch_translate_flat_module_google import parse_key_values_ordered

_FRONTEND = _SCRIPT_DIR.parent

_REF_PATH = _SCRIPT_DIR / "_emit_tier27_canvas_sq_ar_hi.py"
_SPEC = importlib.util.spec_from_file_location("emit_tier27_canvas_ref", _REF_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise SystemExit(f"Cannot load {_REF_PATH}")
_emit_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_emit_mod)

encode_ts_single_quoted = _emit_mod.encode_ts_single_quoted
nl_key_multiline_rows = _emit_mod.nl_key_multiline_rows
parse_values_ordered = _emit_mod.parse_values_ordered

EN_PATH = _FRONTEND / "src/locales/messages/en/canvas.ts"
NL_PATH = _FRONTEND / "src/locales/messages/nl/canvas.ts"

_PARITY_SPEC = importlib.util.spec_from_file_location(
    "i18n_en_parity",
    _SCRIPT_DIR / "analyze_i18n_en_parity.py",
)
if _PARITY_SPEC is None or _PARITY_SPEC.loader is None:
    raise SystemExit("Cannot load analyze_i18n_en_parity.py")
_parity_mod = importlib.util.module_from_spec(_PARITY_SPEC)
_PARITY_SPEC.loader.exec_module(_parity_mod)
_parse_ts_strings_any = _parity_mod.parse_ts_strings


def _load_cur_canvas_values(
    en_keys: list[str],
    en_vals: list[str],
    target_path: Path,
) -> list[str]:
    if not target_path.is_file():
        return list(en_vals)
    try:
        cur = parse_values_ordered(target_path)
        if len(cur) == len(en_vals):
            return cur
    except AssertionError:
        pass
    loc_map = _parse_ts_strings_any(target_path)
    return [loc_map.get(en_keys[i], en_vals[i]) for i in range(len(en_keys))]


def _write_canvas(locale: str, rows: list[tuple[str, bool]], values: list[str]) -> None:
    out_path = _FRONTEND / "src/locales/messages" / locale / "canvas.ts"
    lines = [
        "/**",
        f" * {locale} UI — canvas",
        " */",
        "",
        "export default {",
    ]
    for (key, multiline), val in zip(rows, values, strict=True):
        esc = encode_ts_single_quoted(val)
        if multiline:
            lines.append(f"  '{key}':")
            lines.append(f"    '{esc}',")
        else:
            lines.append(f"  '{key}': '{esc}',")
    lines.append("}")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _would_translate(
    en_vals: list[str],
    cur_vals: list[str],
    force_all: bool,
    index: int,
) -> bool:
    src = en_vals[index]
    if not src.strip():
        return False
    if force_all:
        return True
    return cur_vals[index] == src


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch Google-translate canvas.ts (EN→locale).")
    parser.add_argument(
        "locale",
        help="Folder under locales/messages (e.g. sq, ar, hi).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.35,
        help="Seconds between HTTP calls (default: 0.35).",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="Translate at most this many strings (0 = no limit).",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Replace every value from EN; ignore existing locale edits.",
    )
    parser.add_argument(
        "--google-target",
        default=None,
        help="Override Google `target` code (e.g. zh-CN).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List strings that would be translated; no HTTP and no file write.",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=20.0,
        help="HTTP connect timeout seconds (default: 20).",
    )
    parser.add_argument(
        "--read-timeout",
        type=float,
        default=60.0,
        help="HTTP read timeout seconds (default: 60).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=6,
        help="Attempts per string on network / 429 errors (default: 6).",
    )
    parser.add_argument(
        "--retry-base-delay",
        type=float,
        default=2.0,
        help="Base seconds before retry; backoff is base * 2^attempt (default: 2).",
    )
    args = parser.parse_args()
    if args.retries < 1:
        raise SystemExit("--retries must be at least 1")

    locale = args.locale.strip()
    if not locale:
        raise SystemExit("locale must be non-empty")

    en_pairs = parse_key_values_ordered(EN_PATH)
    en_keys = [key for key, _ in en_pairs]
    en_vals = [val for _, val in en_pairs]
    nl_text = NL_PATH.read_text(encoding="utf-8")
    rows = nl_key_multiline_rows(nl_text)
    if len(rows) != len(en_vals):
        raise SystemExit(f"nl keys {len(rows)} vs en values {len(en_vals)}")
    if len(parse_values_ordered(EN_PATH)) != len(en_vals):
        raise SystemExit("en/canvas.ts entry count mismatch between parsers")

    target_path = _FRONTEND / "src/locales/messages" / locale / "canvas.ts"
    cur_vals = _load_cur_canvas_values(en_keys, en_vals, target_path)
    if len(cur_vals) != len(en_vals):
        raise SystemExit(
            f"{locale} canvas value count {len(cur_vals)} != en {len(en_vals)}",
        )

    if args.dry_run:
        pending = 0
        for index, src in enumerate(en_vals):
            if not _would_translate(en_vals, cur_vals, args.force_all, index):
                continue
            if args.max and pending >= args.max:
                break
            snippet = src.replace("\n", "\\n")
            if len(snippet) > 72:
                snippet = snippet[:72] + "..."
            print(f"  #{index}: {ascii(snippet)}")
            pending += 1
        print(f"dry-run: {pending} string(s) would be translated.")
        return

    tgt_code = google_target(locale, args.google_target)
    translator = GoogleTranslator(source="en", target=tgt_code)
    restore_timeout = patch_requests_timeout(
        args.connect_timeout,
        args.read_timeout,
    )
    out_vals: list[str] = []
    translated = 0
    try:
        for index, src in enumerate(en_vals):
            if not args.force_all and cur_vals[index] != src:
                out_vals.append(cur_vals[index])
                continue
            if not src.strip():
                out_vals.append(src)
                continue
            if args.max and translated >= args.max:
                out_vals.append(cur_vals[index])
                continue

            shielded, ph = shield_placeholders(src)
            try:
                result = translate_with_retries(
                    translator,
                    shielded,
                    retries=args.retries,
                    retry_base_delay=args.retry_base_delay,
                )
            except (
                requests.RequestException,
                TooManyRequests,
                RequestError,
            ) as exc:
                raise SystemExit(
                    f"Translate failed at index {index} after {args.retries} attempt(s): "
                    f"{exc!r}. Check VPN/network, or raise timeouts with "
                    f"--connect-timeout / --read-timeout.",
                ) from exc
            if not result:
                raise SystemExit(f"Empty translation at index {index}")
            out_vals.append(unshield_placeholders(result, ph))
            translated += 1
            time.sleep(args.delay)
    finally:
        restore_timeout()

    _write_canvas(locale, rows, out_vals)
    print(f"Wrote {target_path} ({translated} strings translated via Google).")


if __name__ == "__main__":
    main()
