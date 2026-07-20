"""Live smoke: qwen3.6-flash vision detect + rebuild on synthetic fixtures.

Usage (WSL, from repo root):
  conda activate python313
  python scripts/smoke_vision_mindmap_make_fixtures.py
  PYTHONPATH=. python scripts/smoke_vision_mindmap.py
"""

from __future__ import annotations

import json
from pathlib import Path

from services.knowledge.vision_mindmap import dashscope_vision_mindmap

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Run live vision smoke against local fixtures."""
    fixture_dir = ROOT / "tmp" / "handdrawn_mindmap_smoke"
    mindmap = fixture_dir / "synthetic_mindmap.png"
    document = fixture_dir / "synthetic_document.png"
    if not mindmap.is_file() or not document.is_file():
        print("Fixtures missing. Run: python scripts/smoke_vision_mindmap_make_fixtures.py")
        return 2

    cases = (
        (mindmap, True),
        (document, False),
    )
    all_ok = True
    for path, expect_mindmap in cases:
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        raw = path.read_bytes()
        print(f"\n=== {path.name} (expect_mindmap={expect_mindmap}) ===")
        result = dashscope_vision_mindmap(raw, mime_type=mime, language="en")
        print(f"is_mindmap={result.is_mindmap} confidence={result.confidence:.2f} reason={result.reason!r}")
        if result.spec:
            print(json.dumps(result.spec, ensure_ascii=False, indent=2)[:1200])
        ok = result.is_mindmap is expect_mindmap
        print("PASS" if ok else "FAIL")
        all_ok = all_ok and ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
