"""Decode one animated WebP at a time, scaled to the pet window."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageSequence

DISPLAY_MAX = (260, 340)


class Clip:
    """One action, frames already fitted to the pet window."""

    def __init__(self, path: Path) -> None:
        self.path = path
        frames: list[Image.Image] = []
        durations: list[int] = []
        with Image.open(path) as image:
            for frame in ImageSequence.Iterator(image):
                fitted = frame.convert("RGBA")
                fitted.thumbnail(DISPLAY_MAX, Image.Resampling.LANCZOS)
                frames.append(fitted)
                durations.append(int(frame.info.get("duration") or 83))
        if not frames:
            raise ValueError(f"empty clip {path}")
        self.frames = frames
        self.durations = durations

    def __len__(self) -> int:
        return len(self.frames)


def clip_paths(mascot: str, asset_root: Path) -> list[Path]:
    """WebP files for this mascot, in name order. Nothing is decoded yet."""
    folder = asset_root / mascot
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.glob("*.webp") if path.is_file())


def load_clip(path: Path) -> Clip:
    """Decode a single action."""
    return Clip(path)
