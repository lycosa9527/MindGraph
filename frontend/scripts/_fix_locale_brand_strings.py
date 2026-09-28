"""Keep MindMate and MindGraph as Latin product names in every locale.

Chinese is the source. Where that catalog uses MindMate or MindGraph, every
other locale must keep the same tokens. Diagram-type wording is left alone
because those keys do not contain the product names in Chinese.
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "src", "locales", "messages")
)

BRANDS = ("MindGraph", "MindMate")
EXACT = {"MindMate", "MindGraph", "MindMate AI", "MindMate Dify"}
ENTRY_RE = re.compile(
    r"(?P<prefix>'(?P<key>(?:\\'|[^'])*)'\s*:\s*)"
    r"(?P<quote>['\"])(?P<val>(?:\\.|(?!(?P=quote)).)*)(?P=quote)"
)


def unescape(value: str) -> str:
    return value.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")


def escape_for(value: str, quote: str) -> str:
    escaped = value.replace("\\", "\\\\")
    if quote == "'":
        return escaped.replace("'", "\\'")
    return escaped.replace('"', '\\"')


def brands_required(source: str) -> tuple[str, ...]:
    return tuple(brand for brand in BRANDS if brand in source)


def normalize_brand_case(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        if word.lower() == "mindgraph":
            return "MindGraph"
        if word.lower() == "mindmate":
            return "MindMate"
        return word

    return re.sub(r"(?i)\bmind(?:graph|mate)\b", repl, value)


def load_entries(path: str) -> dict[str, str]:
    text = open(path, encoding="utf-8").read()
    return {match.group("key"): unescape(match.group("val")) for match in ENTRY_RE.finditer(text)}


def load_zh() -> dict[str, str]:
    catalog: dict[str, str] = {}
    zh_dir = os.path.join(ROOT, "zh")
    for name in os.listdir(zh_dir):
        if name.endswith(".ts"):
            catalog.update(load_entries(os.path.join(zh_dir, name)))
    return catalog


def harvest_aliases(locale: str, zh: dict[str, str]) -> list[tuple[str, str]]:
    """Translations of the bare product name, longest first."""
    found: dict[str, str] = {}
    locale_dir = os.path.join(ROOT, locale)
    for name in os.listdir(locale_dir):
        if not name.endswith(".ts"):
            continue
        for key, value in load_entries(os.path.join(locale_dir, name)).items():
            source = zh.get(key)
            if source not in ("MindMate", "MindGraph"):
                continue
            if value == source or value.startswith("__"):
                continue
            if len(value) < 2 or len(value) > 40:
                continue
            found[value] = source
    return sorted(found.items(), key=lambda item: len(item[0]), reverse=True)


def apply_aliases(value: str, aliases: list[tuple[str, str]]) -> str:
    updated = value
    for alias, canonical in aliases:
        if alias and alias in updated:
            updated = updated.replace(alias, canonical)
    return updated


def insert_missing_brands(value: str, required: tuple[str, ...]) -> str:
    updated = value
    for brand in required:
        if brand in updated:
            continue
        if re.search(r"\bAI\b", updated):
            updated = re.sub(r"\bAI\b", f"{brand} AI", updated, count=1)
            continue
        if "home page" in updated:
            updated = updated.replace("home page", f"{brand} home page", 1)
            continue
        for separator in (": ", "："):
            if separator in updated:
                head, tail = updated.split(separator, 1)
                updated = f"{head}{separator}{brand} {tail}"
                break
        else:
            updated = f"{brand} {updated}".strip() if updated else brand
    return updated


def untack_brand_suffix(value: str) -> str:
    """Turn a trailing ' (MindGraph)' into the name inside the sentence."""
    updated = value
    for brand in BRANDS:
        suffix = f" ({brand})"
        if not updated.endswith(suffix):
            continue
        body = updated[: -len(suffix)].rstrip()
        if brand in body:
            return body
        return insert_missing_brands(body, (brand,))
    return updated


def rewrite_file(path: str, zh: dict[str, str], aliases: list[tuple[str, str]]) -> bool:
    original = open(path, encoding="utf-8").read()

    def repl(match: re.Match[str]) -> str:
        key = match.group("key")
        source = zh.get(key)
        if not source:
            return match.group(0)
        required = brands_required(source)
        if not required:
            return match.group(0)
        current = unescape(match.group("val"))
        if source in EXACT:
            updated = source
        else:
            updated = untack_brand_suffix(current)
            updated = normalize_brand_case(apply_aliases(updated, aliases))
            if any(brand not in updated for brand in required):
                updated = insert_missing_brands(updated, required)
            updated = normalize_brand_case(updated)
        if updated == current:
            return match.group(0)
        quote = match.group("quote")
        if quote == "'" and "'" in updated and '"' not in updated:
            quote = '"'
        if quote == '"' and '"' in updated and "'" not in updated:
            quote = "'"
        return f"{match.group('prefix')}{quote}{escape_for(updated, quote)}{quote}"

    rewritten = ENTRY_RE.sub(repl, original)
    if rewritten == original:
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(rewritten)
    return True


def main() -> int:
    zh = load_zh()
    touched = 0
    for locale in sorted(os.listdir(ROOT)):
        locale_dir = os.path.join(ROOT, locale)
        if not os.path.isdir(locale_dir) or locale == "__test__":
            continue
        aliases = [] if locale == "zh" else harvest_aliases(locale, zh)
        for name in sorted(os.listdir(locale_dir)):
            if not name.endswith(".ts"):
                continue
            if rewrite_file(os.path.join(locale_dir, name), zh, aliases):
                touched += 1
    print(f"updated {touched} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
