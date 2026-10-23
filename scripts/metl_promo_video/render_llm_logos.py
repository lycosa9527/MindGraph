#!/usr/bin/env python3
"""PNG marks for DeepSeek, Qwen, Doubao, Zhipu (same SVG as MindGraph canvas menu)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from services.infrastructure.utils.browser import BrowserContextManager

ASSET = Path(__file__).resolve().parent / "assets" / "llm_logos.html"
DEFAULT_OUT = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-v2/logos")
NAMES = ("deepseek", "qwen", "doubao", "zhipu")


async def render_one(name: str, dest: Path) -> None:
    """Screenshot one logo on dark background."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = ASSET.as_uri() + f"?logo={name}"
    async with BrowserContextManager() as context:
        page = await context.new_page()
        await page.set_viewport_size({"width": 512, "height": 512})
        await page.goto(url, wait_until="networkidle")
        await page.locator(".icon").screenshot(path=str(dest))
    print(f"logo {dest.name} {dest.stat().st_size}", flush=True)


async def render_all(out_dir: Path) -> None:
    """Write four PNG reference marks."""
    for name in NAMES:
        await render_one(name, out_dir / f"{name}.png")


def main() -> None:
    """CLI entry."""
    asyncio.run(render_all(DEFAULT_OUT))


if __name__ == "__main__":
    main()
