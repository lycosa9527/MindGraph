"""Public /auth cinematic clip ids. Keep in sync with the login-video catalog."""

from __future__ import annotations

LOGIN_HERO_CLIPS: tuple[str, ...] = (
    "01-awaken-cosmos",
    "02-mind-leap",
    "03-study-light",
    "04-ai-lab",
)
LOGIN_HERO_CLIP_SET = frozenset(LOGIN_HERO_CLIPS)
LOGIN_HERO_CONTENT_TYPE = "video/mp4"


def parse_hero_clip_id(raw: str) -> str:
    """Accept ``01-awaken-cosmos.mp4`` or a short ``01`` id."""
    stem = raw.strip()
    if stem.endswith(".mp4"):
        stem = stem[:-4]
    if stem in LOGIN_HERO_CLIP_SET:
        return stem
    if len(stem) == 2:
        for clip_id in LOGIN_HERO_CLIPS:
            if clip_id.startswith(f"{stem}-"):
                return clip_id
    raise ValueError(f"Unknown login hero: {raw}")
