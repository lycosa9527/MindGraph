#!/usr/bin/env python3
"""Export MindGraph diagram PNGs for the METL promo montage.

Requires Playwright Chromium and a running SPA:

  FRONTEND_URL=http://127.0.0.1:5173  # Vite dev, or omit to use PORT (default 9527)

Example:

  python -m scripts.metl_promo_video.export_stills \\
    --out /mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-hybrid/diagrams
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import Error as PlaywrightError

from routers.api.vueflow_screenshot import capture_diagram_screenshot
from scripts.metl_promo_video.specs import PROMO_DIAGRAMS
from services.diagram.semantic_spec_validation import ensure_valid_semantic_spec

DEFAULT_OUT = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-hybrid/diagrams")
VIEW_W = 1920
VIEW_H = 1080


async def export_one(diagram_type: str, data: dict, dest: Path) -> None:
    """Validate spec, render via ExportRenderPage, write PNG."""
    ensure_valid_semantic_spec(diagram_type, data)
    png = await capture_diagram_screenshot(
        diagram_data=data,
        diagram_type=diagram_type,
        width=VIEW_W,
        height=VIEW_H,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(png)
    print(f"png {dest.name} {len(png)}", flush=True)


async def run_all(out_dir: Path, force: bool, only_slug: str) -> None:
    """Export every promo diagram unless PNG already exists."""
    manifest: list[dict[str, str]] = []
    rows = PROMO_DIAGRAMS
    if only_slug:
        rows = tuple(row for row in PROMO_DIAGRAMS if row["slug"] == only_slug)
        if not rows:
            raise ValueError(f"unknown slug {only_slug}")
    for row in rows:
        dest = out_dir / f"{row['slug']}.png"
        if dest.is_file() and dest.stat().st_size > 5000 and not force:
            print(f"skip {dest.name}", flush=True)
            continue
        try:
            await export_one(row["diagram_type"], row["data"], dest)
        except (TimeoutError, PlaywrightError, OSError, RuntimeError) as exc:
            if row["slug"] == "07-multi_flow_map":
                print(f"warn {row['slug']} export failed: {exc}", flush=True)
                continue
            raise
    for row in PROMO_DIAGRAMS:
        dest = out_dir / f"{row['slug']}.png"
        if not dest.is_file():
            continue
        manifest.append(
            {
                "slug": row["slug"],
                "diagram_type": row["diagram_type"],
                "label_zh": row["label_zh"],
                "file": dest.name,
            }
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="Export promo diagram PNGs")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--slug", default="", help="Export one slug only, e.g. 07-multi_flow_map")
    args = parser.parse_args()
    asyncio.run(run_all(args.out, args.force, args.slug.strip()))


if __name__ == "__main__":
    main()
