"""Key green-screen stills onto dark plates and trim Wan reference openings."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.training_roles.export import key_green

PLATE_SIZE = (1920, 1080)
PLATE_COLOR = (8, 15, 32)
GREEN_SHARE = 0.42
PROBE_FRAMES = 45


def ffmpeg_bin() -> str:
    """Use system or conda ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError("ffmpeg not on PATH")


def write_character_plate(still: Path, dest: Path) -> Path:
    """Composite a keyed still onto a 16:9 dark plate so Wan cannot open on green."""
    keyed = key_green(Image.open(still))
    plate = Image.new("RGBA", PLATE_SIZE, (*PLATE_COLOR, 255))
    max_h = int(PLATE_SIZE[1] * 0.78)
    scale = min(max_h / keyed.height, (PLATE_SIZE[0] * 0.42) / keyed.width)
    width = max(1, int(keyed.width * scale))
    height = max(1, int(keyed.height * scale))
    cat = keyed.resize((width, height), Image.Resampling.LANCZOS)
    left = int(PLATE_SIZE[0] * 0.18 - width / 2)
    top = (PLATE_SIZE[1] - height) // 2
    plate.alpha_composite(cat, (max(0, left), max(0, top)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    plate.convert("RGB").save(dest, format="JPEG", quality=92, optimize=True)
    return dest


def _run_ffmpeg(args: list[str], label: str) -> None:
    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "ffmpeg failed"
        raise RuntimeError(f"{label}: {tail}")


def _frame_is_green(path: Path) -> bool:
    pixels = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    greenness = green - np.maximum(red, blue)
    mask = (green > 90) & (greenness > 28) & (green > red + 20) & (green > blue + 20)
    return float(mask.mean()) > GREEN_SHARE


def leading_green_seconds(mp4: Path, work_dir: Path) -> float:
    """How many seconds at the start are still the green-screen identity plate."""
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
    frames = sorted(probe.glob("*.jpg"))
    leading = 0
    for frame in frames:
        if not _frame_is_green(frame):
            break
        leading += 1
    if leading == 0:
        return 0.0
    return leading / 30.0


def reencode_login_clip(mp4: Path, dest: Path, work_dir: Path) -> Path:
    """CRF 18 1080P video-only encode; drop a green-screen identity open when present."""
    seconds = leading_green_seconds(mp4, work_dir)
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
