"""Batch-translate a single flat message module (one line per key) EN→locale.

Skips `canvas.ts` — use `batch_translate_canvas_google.py` (NL multiline layout).

Run from repo root:
  python frontend/scripts/batch_translate_flat_module_google.py sq notification.ts
"""

from __future__ import annotations

import argparse
import importlib.util
import re
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

_FRONTEND = _SCRIPT_DIR.parent

_REF_PATH = _SCRIPT_DIR / "_emit_tier27_canvas_sq_ar_hi.py"
_SPEC = importlib.util.spec_from_file_location("emit_tier27_canvas_ref", _REF_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise SystemExit(f"Cannot load {_REF_PATH}")
_emit_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_emit_mod)

_PARITY_SPEC = importlib.util.spec_from_file_location(
    "i18n_en_parity",
    _SCRIPT_DIR / "analyze_i18n_en_parity.py",
)
if _PARITY_SPEC is None or _PARITY_SPEC.loader is None:
    raise SystemExit("Cannot load analyze_i18n_en_parity.py")
_parity_mod = importlib.util.module_from_spec(_PARITY_SPEC)
_PARITY_SPEC.loader.exec_module(_parity_mod)

decode_ts_string = _emit_mod.decode_ts_string
encode_ts_single_quoted = _emit_mod.encode_ts_single_quoted


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


def parse_key_values_ordered(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    body = text.split("export default {", 1)[1].rsplit("}", 1)[0]
    lines = body.splitlines()
    result: list[tuple[str, str]] = []
    idx = 0
    while idx < len(lines):
        match = re.match(r"^\s*'([^']+)':\s*(.*)$", lines[idx].rstrip())
        if not match:
            idx += 1
            continue
        key, rest = match.group(1), match.group(2).strip()
        if rest == "":
            idx += 1
            val_line = lines[idx].strip()
            if val_line.endswith(","):
                val_line = val_line[:-1].strip()
            if val_line.startswith("'") and val_line.endswith("'"):
                decoded = decode_ts_string(val_line[1:-1])
            elif val_line.startswith('"') and val_line.endswith('"'):
                decoded = _unescape_double_quoted(val_line[1:-1])
            else:
                raise ValueError(f"Bad multiline value for {key} in {path}")
            result.append((key, decoded))
            idx += 1
        else:
            raw = rest
            if raw.endswith(","):
                raw = raw[:-1].strip()
            if raw.startswith("'") and raw.endswith("'"):
                decoded = decode_ts_string(raw[1:-1])
            elif raw.startswith('"') and raw.endswith('"'):
                decoded = _unescape_double_quoted(raw[1:-1])
            else:
                raise ValueError(f"Bad value for {key} in {path}")
            result.append((key, decoded))
            idx += 1
    return result


def _write_flat_module(locale: str, module: str, pairs: list[tuple[str, str]]) -> None:
    stem = module.removesuffix(".ts")
    out_path = _FRONTEND / "src/locales/messages" / locale / module
    lines = [
        "/**",
        f" * {locale} UI — {stem}",
        " */",
        "",
        "export default {",
    ]
    for index, (key, val) in enumerate(pairs):
        esc = encode_ts_single_quoted(val)
        if index == len(pairs) - 1:
            lines.append(f"  '{key}': '{esc}'")
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
    parser = argparse.ArgumentParser(
        description="Batch Google-translate a flat messages/*.ts module (not canvas).",
    )
    parser.add_argument("locale", help="e.g. sq, ar, az")
    parser.add_argument(
        "module",
        help="Filename e.g. notification.ts, sidebar.ts, common.ts",
    )
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--max", type=int, default=0)
    parser.add_argument("--force-all", action="store_true")
    parser.add_argument("--google-target", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--connect-timeout", type=float, default=20.0)
    parser.add_argument("--read-timeout", type=float, default=60.0)
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument("--retry-base-delay", type=float, default=2.0)
    args = parser.parse_args()
    if args.retries < 1:
        raise SystemExit("--retries must be at least 1")

    locale = args.locale.strip()
    module = args.module.strip()
    if not locale or not module:
        raise SystemExit("locale and module required")
    if module == "canvas.ts":
        raise SystemExit("Use batch_translate_canvas_google.py for canvas.ts")
    if not module.endswith(".ts"):
        raise SystemExit("module must end with .ts")

    en_path = _FRONTEND / "src/locales/messages/en" / module
    if not en_path.is_file():
        raise SystemExit(f"Missing {en_path}")

    en_pairs = parse_key_values_ordered(en_path)
    en_keys = [k for k, _ in en_pairs]
    en_vals = [v for _, v in en_pairs]

    target_path = _FRONTEND / "src/locales/messages" / locale / module
    if target_path.is_file():
        try:
            cur_pairs = parse_key_values_ordered(target_path)
            cur_keys = [k for k, _ in cur_pairs]
            if len(cur_pairs) != len(en_pairs) or cur_keys != en_keys:
                raise ValueError("locale keys not aligned to en")
            cur_vals = [v for _, v in cur_pairs]
        except ValueError:
            blob = _parity_mod.parse_ts_strings(target_path)
            cur_vals = [blob.get(en_keys[i], en_vals[i]) for i in range(len(en_keys))]
    else:
        cur_vals = list(en_vals)

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
            print(f"  #{index} {en_keys[index]}: {ascii(snippet)}")
            pending += 1
        print(f"dry-run: {pending} string(s) would be translated.")
        return

    tgt_code = google_target(locale, args.google_target)
    translator = GoogleTranslator(source="en", target=tgt_code)
    restore_timeout = patch_requests_timeout(
        args.connect_timeout,
        args.read_timeout,
    )
    out_pairs: list[tuple[str, str]] = []
    translated = 0
    try:
        for index, key in enumerate(en_keys):
            src = en_vals[index]
            if not args.force_all and cur_vals[index] != src:
                out_pairs.append((key, cur_vals[index]))
                continue
            if not src.strip():
                out_pairs.append((key, src))
                continue
            if args.max and translated >= args.max:
                out_pairs.append((key, cur_vals[index]))
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
                    f"Translate failed at {key} after {args.retries} attempt(s): {exc!r}",
                ) from exc
            if not result:
                raise SystemExit(f"Empty translation at {key}")
            out_pairs.append((key, unshield_placeholders(result, ph)))
            translated += 1
            time.sleep(args.delay)
    finally:
        restore_timeout()

    _write_flat_module(locale, module, out_pairs)
    print(f"Wrote {target_path} ({translated} strings translated via Google).")


if __name__ == "__main__":
    main()
