"""Training course constants and seed identifiers."""

from __future__ import annotations

STEP_TYPES = frozenset({"canvas", "slide", "video", "page"})
PAGE_KEYS = frozenset(
    {
        "auth",
        "mindgraph",
        "canvas",
        "mindmate",
        "askonce",
        "maite",
        "debateverse",
        "zhihui",
        "library",
        "template",
        "course",
        "knowledge",
        "showcase",
        "community",
        "voice-notes",
        "thinking-coins",
    }
)
COURSE_STATUSES = frozenset({"draft", "ready"})
MODAL_KEYS = frozenset(
    {
        "language-settings",
        "account",
        "thinking-coins",
        "update-log",
        "login",
        "online-collab",
        "export-community",
    }
)
DIAGRAM_FOCUS_TYPES = (
    "circle_map",
    "bubble_map",
    "double_bubble_map",
    "tree_map",
    "brace_map",
    "flow_map",
    "multi_flow_map",
    "bridge_map",
    "mindmap",
    "concept_map",
)
FOCUS_KEYS = frozenset(
    {f"diagram-{name}" for name in DIAGRAM_FOCUS_TYPES}
    | {
        "mindmap-v1",
        "mindmap-v2",
        "mindmap-v3",
        "auth-login",
        "auth-register",
        "canvas-add",
        "canvas-delete",
    }
)
MINDMAP_CANVAS_MODES = frozenset({"legacy", "v2"})


def normalize_mindmap_canvas_mode(value: object) -> str | None:
    """Accept leftover stored ``v3`` as New canvas; reject unknown ids."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text == "v3":
        return "v2"
    if text not in MINDMAP_CANVAS_MODES:
        raise ValueError(f"Invalid mindmap_canvas_mode: {text}")
    return text


def optional_step_key(value: object, allowed: frozenset[str], label: str) -> str | None:
    """Strip empty catalog keys; reject unknown values."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text not in allowed:
        raise ValueError(f"Invalid {label}: {text}")
    return text


def optional_notes(value: object) -> str:
    """Trim step notes; reject oversized payloads."""
    text = str(value or "").strip()
    if len(text) > 4000:
        raise ValueError("notes too long")
    return text


MARK_STEPS_MIN = 1
MARK_STEPS_MAX = 8


def clamped_mark_step(value: object, default: int = 1) -> int:
    """Keep intra-slide mark steps in 1..8."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        number = int(value)
    except ValueError:
        return default
    return min(MARK_STEPS_MAX, max(MARK_STEPS_MIN, number))


DOUBLE_BUBBLE_COURSE_ID = "6f2a1c90-db01-4000-8000-00000000db01"
DOUBLE_BUBBLE_STEP_ID = "6f2a1c90-db01-4000-8000-00000000db02"
DOUBLE_BUBBLE_COVER_ID = "6f2a1c90-db01-4000-8000-00000000db03"

DOUBLE_BUBBLE_TITLE = {
    "zh": "双气泡图教程",
    "en": "Double Bubble Map tutorial",
}
DOUBLE_BUBBLE_DESCRIPTION = {
    "zh": "对比辨析两个对象。",
    "en": "Compare and contrast two topics.",
}
DOUBLE_BUBBLE_OPTIONS = [
    {"id": "ice-water", "label": "ice vs water", "item_a": "ice", "item_b": "water"},
    {"id": "ipv4-ipv6", "label": "IPv4 vs IPv6", "item_a": "IPv4", "item_b": "IPv6"},
]

IMAGE_MIME = frozenset({"image/png", "image/jpeg", "image/webp"})
SLIDE_MIME = IMAGE_MIME | frozenset({"application/pdf"})
VIDEO_MIME = frozenset({"video/mp4", "video/webm", "video/quicktime"})
MEDIA_MIME = SLIDE_MIME | VIDEO_MIME

ROLE_MIME = {
    "cover": IMAGE_MIME,
    "slide": SLIDE_MIME,
    "video": VIDEO_MIME,
    "media": MEDIA_MIME,
    "thumb": IMAGE_MIME,
}
ROLE_MAX_BYTES = {
    "cover": 20 * 1024 * 1024,
    "slide": 20 * 1024 * 1024,
    "video": 100 * 1024 * 1024,
    "media": 100 * 1024 * 1024,
    "thumb": 2 * 1024 * 1024,
}
