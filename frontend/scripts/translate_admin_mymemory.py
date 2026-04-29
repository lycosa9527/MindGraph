"""Translate en/admin.ts via MyMemory API with disk cache. Run from repo root:
  python frontend/scripts/translate_admin_mymemory.py id
  python frontend/scripts/translate_admin_mymemory.py hi vi ms tl sq
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_ADMIN = ROOT / "src/locales/messages/en/admin.ts"
CACHE_PATH = Path(__file__).resolve().parent / ".admin_translate_mymemory_cache.json"

LINE_RE = re.compile(
    r"^  '((?:[^'\\]|\\.)+)':\s*'((?:\\'|[^'])*)',?\s*$"
)
CHINESE_OR_FW = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]|[\u3010\u3011]")


def parse_en_admin(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    pairs: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        m = LINE_RE.match(line)
        if not m:
            continue
        key = m.group(1).replace("\\'", "'")
        raw_val = m.group(2)
        val = (
            raw_val.replace("\\\\", "\x00BACKSLASH\x00")
            .replace("\\n", "\n")
            .replace("\\'", "'")
            .replace("\x00BACKSLASH\x00", "\\")
        )
        pairs.append((key, val))
    return pairs


def load_cache() -> dict[str, str]:
    if not CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")


def ts_escape(val: str) -> str:
    return (
        val.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
    )


def translate_mymemory(text: str, lang: str, cache: dict[str, str]) -> str:
    ck = f"{lang}::{text}"
    if ck in cache:
        return cache[ck]
    if len(text) > 450:
        text = text[:450]
    q = urllib.parse.quote(text)
    url = f"https://api.mymemory.translated.net/get?q={q}&langpair=en|{lang}"
    req = urllib.request.Request(url, headers={"User-Agent": "MindGraph-i18n/1.0"})
    last_err: Exception | None = None
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
            out = data.get("responseData", {}).get("translatedText", "")
            if out and out.upper() != text.upper():
                cache[ck] = out
                if len(cache) % 25 == 0:
                    save_cache(cache)
                return out
            return text
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionResetError, OSError) as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    print("translate failed, using EN:", lang, repr(text[:50]), last_err)
    return text


def passthrough(key: str, en_val: str) -> bool:
    if key == "admin.feature.workshopChat":
        return True
    return bool(CHINESE_OR_FW.search(en_val))


def write_locale(locale: str, pairs: list[tuple[str, str]], cache: dict[str, str]) -> None:
    lang = "tl" if locale == "tl" else locale
    out_lines = [
        "/**",
        f" * {locale} UI — admin",
        " */",
        "",
        "export default {",
    ]
    dest = ROOT / "src" / "locales" / "messages" / locale / "admin.ts"
    dest.parent.mkdir(parents=True, exist_ok=True)

    for i, (key, en_val) in enumerate(pairs):
        if passthrough(key, en_val):
            tr = en_val
        else:
            tr = translate_mymemory(en_val, lang, cache)
        out_lines.append(f"  '{key}': '{ts_escape(tr)}',")
        if (i + 1) % 20 == 0:
            print(f"  ... {i + 1}/{len(pairs)}")
        time.sleep(0.45)

    out_lines.append("}")
    out_lines.append("")
    dest.write_text("\n".join(out_lines), encoding="utf-8")
    save_cache(cache)
    print(f"Wrote {dest} ({len(pairs)} keys)")


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "--count":
        pairs = parse_en_admin(EN_ADMIN)
        print(len(pairs))
        return
    if len(sys.argv) < 2:
        print("Usage: translate_admin_mymemory.py <locale> [locale ...]")
        sys.exit(1)
    pairs = parse_en_admin(EN_ADMIN)
    print("parsed keys:", len(pairs))
    if len(pairs) < 100:
        print("Parse error: too few keys")
        sys.exit(1)
    cache = load_cache()
    for loc in sys.argv[1:]:
        print(f"=== {loc} ===")
        write_locale(loc, pairs, cache)
    save_cache(cache)


if __name__ == "__main__":
    main()
