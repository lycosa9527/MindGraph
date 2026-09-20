#!/usr/bin/env python3
"""Compress the default /auth still into frontend/public.

Source: Pictures/mascots/auth-login/still-options/o-writing-tablet.jpg

  python -m scripts.auth_login_video.ship_stills
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from scripts.auth_login_video.paths import PUBLIC_AUTH_DIR, SHIPPED_STILL, STILL_OPTIONS_DIR

DEFAULT_STILL_ID = "o-writing-tablet"
STILL_MAX_WIDTH = 1920
STILL_WEBP_QUALITY = 78
STILL_WEBP_METHOD = 4


def default_still_source() -> Path:
    """Desktop still chosen as the local-dev /auth background."""
    return STILL_OPTIONS_DIR / f"{DEFAULT_STILL_ID}.jpg"


def compress_still(source: Path, dest: Path) -> None:
    """Write a 1080p-capped WebP poster for first paint."""
    image = Image.open(source).convert("RGB")
    if image.width > STILL_MAX_WIDTH:
        height = round(image.height * STILL_MAX_WIDTH / image.width)
        image = image.resize((STILL_MAX_WIDTH, height), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        dest,
        format="WEBP",
        quality=STILL_WEBP_QUALITY,
        method=STILL_WEBP_METHOD,
    )


def ship_stills() -> None:
    """Write login-hero.webp and remove leftover stills from public."""
    source = default_still_source()
    if not source.is_file():
        raise FileNotFoundError(source)
    PUBLIC_AUTH_DIR.mkdir(parents=True, exist_ok=True)
    compress_still(source, SHIPPED_STILL)
    for leftover in PUBLIC_AUTH_DIR.iterdir():
        if leftover == SHIPPED_STILL or leftover.name == ".gitkeep":
            continue
        if leftover.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            leftover.unlink()
    print(f"shipped {SHIPPED_STILL} {SHIPPED_STILL.stat().st_size}", flush=True)


def main() -> None:
    """CLI: ship the single default still."""
    ship_stills()
    print("ship-stills-done", flush=True)


if __name__ == "__main__":
    main()
