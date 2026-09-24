"""Key green-screen stills onto dark plates and trim Wan identity opens."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.training_roles.export import crop_union, key_green

PLATE_SIZE = (1920, 1080)
PLATE_COLOR = (8, 15, 32)
GREEN_SHARE = 0.38
CORNER_DARK_SHARE = 0.85
PROBE_FRAMES = 60


def ffmpeg_bin() -> str:
    """Use system ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError("ffmpeg not on PATH")


def write_character_plate(still: Path, dest: Path) -> Path:
    """Composite one keyed still onto a 16:9 dark plate."""
    cropped = crop_union([key_green(Image.open(still))], pad=16)[0]
    plate = Image.new("RGBA", PLATE_SIZE, (*PLATE_COLOR, 255))
    max_h = int(PLATE_SIZE[1] * 0.84)
    scale = min(max_h / cropped.height, (PLATE_SIZE[0] * 0.38) / cropped.width)
    width = max(1, int(cropped.width * scale))
    height = max(1, int(cropped.height * scale))
    character = cropped.resize((width, height), Image.Resampling.LANCZOS)
    left = (PLATE_SIZE[0] - width) // 2
    top = (PLATE_SIZE[1] - height) // 2
    plate.alpha_composite(character, (max(0, left), max(0, top)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    plate.convert("RGB").save(dest, format="JPEG", quality=88, optimize=True)
    return dest


def write_lineup_plate(stills: list[Path], dest: Path) -> Path:
    """Fallback: all roles in one identity sheet if five refs are rejected."""
    keyed = [crop_union([key_green(Image.open(still))], pad=12)[0] for still in stills]
    plate = Image.new("RGBA", PLATE_SIZE, (*PLATE_COLOR, 255))
    count = max(1, len(keyed))
    slot = PLATE_SIZE[0] // count
    max_h = int(PLATE_SIZE[1] * 0.78)
    for index, image in enumerate(keyed):
        scale = min(max_h / image.height, (slot * 0.86) / image.width)
        width = max(1, int(image.width * scale))
        height = max(1, int(image.height * scale))
        character = image.resize((width, height), Image.Resampling.LANCZOS)
        left = slot * index + (slot - width) // 2
        top = (PLATE_SIZE[1] - height) // 2
        plate.alpha_composite(character, (max(0, left), max(0, top)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    plate.convert("RGB").save(dest, format="JPEG", quality=88, optimize=True)
    return dest


def _run_ffmpeg(args: list[str], label: str) -> None:
    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "ffmpeg failed"
        raise RuntimeError(f"{label}: {tail}")


def _frame_is_green(pixels: np.ndarray) -> bool:
    red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    greenness = green - np.maximum(red, blue)
    mask = (green > 90) & (greenness > 28) & (green > red + 20) & (green > blue + 20)
    return float(mask.mean()) > GREEN_SHARE


def _frame_is_dark_plate(pixels: np.ndarray) -> bool:
    height = pixels.shape[0]
    band = max(8, height // 12)
    corners = np.concatenate(
        [
            pixels[:band, :band].reshape(-1, 3),
            pixels[:band, -band:].reshape(-1, 3),
            pixels[-band:, :band].reshape(-1, 3),
            pixels[-band:, -band:].reshape(-1, 3),
        ]
    )
    dark = (corners[:, 0] < 40) & (corners[:, 1] < 50) & (corners[:, 2] < 70)
    return float(dark.mean()) > CORNER_DARK_SHARE


def _is_reference_frame(path: Path) -> bool:
    pixels = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    return _frame_is_green(pixels) or _frame_is_dark_plate(pixels)


def leading_reference_seconds(mp4: Path, work_dir: Path) -> float:
    """Seconds of green-screen, dark-plate, or frozen identity open."""
    probe = work_dir / f"{mp4.stem}-open"
    if probe.exists():
        shutil.rmtree(probe)
    probe.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg(
        [
            ffmpeg_bin(),
            "-y",
            "-i",
            str(mp4),
            "-vf",
            f"select='lte(n\\,{PROBE_FRAMES - 1})'",
            "-frames:v",
            str(PROBE_FRAMES),
            "-fps_mode",
            "vfr",
            str(probe / "%03d.jpg"),
        ],
        f"probe {mp4.name}",
    )
    leading = 0
    for frame in sorted(probe.glob("*.jpg")):
        if not _is_reference_frame(frame):
            break
        leading += 1
    if leading == 0:
        return 0.0
    return leading / 30.0


def reencode_clip(mp4: Path, dest: Path, work_dir: Path) -> Path:
    """CRF 18 1080P video-only encode; drop a reference-image open when present."""
    seconds = leading_reference_seconds(mp4, work_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = [ffmpeg_bin(), "-y", "-i", str(mp4)]
    if seconds > 0.04:
        args.extend(["-ss", f"{seconds:.3f}"])
    args.extend(
        [
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "fast",
            "-an",
            str(dest),
        ]
    )
    _run_ffmpeg(args, f"reencode {mp4.name}")
    trimmed = f" -{seconds:.2f}s" if seconds > 0.04 else ""
    print(
        f"reencode {mp4.name}{trimmed} -> {dest.name} {dest.stat().st_size}",
        flush=True,
    )
    return dest
