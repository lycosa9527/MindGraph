"""Download sample mind-map images for vision smoke tests."""

from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "handdrawn_mindmap_smoke"

URLS = {
    "mm_guidelines.png": (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/"
        "6/64/MindMapGuidelines.svg/640px-MindMapGuidelines.svg.png"
    ),
    "mm_example.png": (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Mind_map_example.svg/640px-Mind_map_example.svg.png"
    ),
    "concept_map.jpg": (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/"
        "5/58/Concept_map_about_concept_maps.jpg/"
        "640px-Concept_map_about_concept_maps.jpg"
    ),
}


def main() -> None:
    """Fetch fixture images with a Wikimedia-friendly User-Agent."""
    OUT.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "MindGraphSmoke/1.0 (local vision test)")]
    urllib.request.install_opener(opener)
    for name, url in URLS.items():
        dest = OUT / name
        print(f"fetch {name}")
        urllib.request.urlretrieve(url, dest)
        print(f"  ok {dest.stat().st_size} bytes")
    print("done", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
