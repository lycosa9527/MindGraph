#!/usr/bin/env python3
"""Copy the default local /auth still into frontend/public.

Source: Pictures/mascots/auth-login/still-options/b-warm-study.jpg

  python -m scripts.auth_login_video.ship_stills
"""

from __future__ import annotations

from scripts.auth_login_video.paths import PUBLIC_AUTH_DIR, SHIPPED_STILL, STILL_OPTIONS_DIR

DEFAULT_STILL_ID = "b-warm-study"


def default_still_source():
    """Desktop still chosen as the local-dev /auth background."""
    return STILL_OPTIONS_DIR / f"{DEFAULT_STILL_ID}.jpg"


def ship_stills() -> None:
    """Write login-hero.png and remove leftover option stills from public."""
    source = default_still_source()
    if not source.is_file():
        raise FileNotFoundError(source)
    PUBLIC_AUTH_DIR.mkdir(parents=True, exist_ok=True)
    SHIPPED_STILL.write_bytes(source.read_bytes())
    for leftover in PUBLIC_AUTH_DIR.glob("*.png"):
        if leftover != SHIPPED_STILL:
            leftover.unlink()
    print(f"shipped {SHIPPED_STILL} {SHIPPED_STILL.stat().st_size}", flush=True)


def main() -> None:
    """CLI: ship the single default still."""
    ship_stills()
    print("ship-stills-done", flush=True)


if __name__ == "__main__":
    main()
