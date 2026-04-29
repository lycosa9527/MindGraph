# -*- coding: utf-8 -*-
"""Compare entry counts between en and uz canvas locale files."""
from __future__ import annotations

from pathlib import Path


def count_entries(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("'") and ": '" in stripped:
            count += 1
    return count


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    en_path = root / "frontend" / "src" / "locales" / "messages" / "en" / "canvas.ts"
    uz_path = root / "frontend" / "src" / "locales" / "messages" / "uz" / "canvas.ts"
    en_count = count_entries(en_path)
    uz_count = count_entries(uz_path)
    print("en", en_count)
    print("uz", uz_count)
    raise SystemExit(0 if en_count == uz_count else 1)


if __name__ == "__main__":
    main()
