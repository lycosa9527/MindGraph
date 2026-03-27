"""Translate canvas-en-flat.json to tier-2 locales; preserves {placeholders}."""
import json
import re
import sys
import time
from pathlib import Path

from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parent
EN_PATH = ROOT / "canvas-en-flat.json"

LOCALE_TARGETS = {
    "hi": "hi",
    "id": "id",
    "vi": "vi",
    "tr": "tr",
    "pl": "pl",
    "uk": "uk",
    "ms": "ms",
}

TOKEN_RE = re.compile(r"(\{[^{}]+\})")


def protect_placeholders(text: str) -> tuple[str, list[str]]:
    """Replace {x} with sentinel tokens for safer machine translation."""
    tokens: list[str] = []

    def repl(m: re.Match) -> str:
        tokens.append(m.group(1))
        return f"⟦{len(tokens) - 1}⟧"

    out = TOKEN_RE.sub(repl, text)
    return out, tokens


def restore_placeholders(text: str, tokens: list[str]) -> str:
    out = text
    for i, tok in enumerate(tokens):
        out = out.replace(f"⟦{i}⟧", tok)
    return out


def translate_value(translator: GoogleTranslator, value: str) -> str:
    if not value.strip():
        return value
    protected, tokens = protect_placeholders(value)
    try:
        translated = translator.translate(protected)
    except Exception:
        time.sleep(0.5)
        translated = translator.translate(protected)
    return restore_placeholders(translated, tokens)


def main() -> None:
    locale = sys.argv[1] if len(sys.argv) > 1 else None
    if not locale or locale not in LOCALE_TARGETS:
        print("Usage: python translate_canvas_tier2.py <hi|id|vi|tr|pl|uk|ms>")
        sys.exit(1)
    target = LOCALE_TARGETS[locale]
    data = json.loads(EN_PATH.read_text(encoding="utf-8"))
    translator = GoogleTranslator(source="en", target=target)
    out: dict[str, str] = {}
    keys = list(data.keys())
    for i, k in enumerate(keys):
        v = data[k]
        out[k] = translate_value(translator, v)
        if (i + 1) % 40 == 0:
            print(f"  {i + 1}/{len(keys)}", flush=True)
            time.sleep(0.3)
    out_path = ROOT / f"canvas-{locale}-flat.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote", out_path, "keys", len(out))


if __name__ == "__main__":
    main()
