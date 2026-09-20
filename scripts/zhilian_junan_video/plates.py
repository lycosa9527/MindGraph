"""Clean Doubao watermarks and pull environment stills for Wan 3.0."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.zhilian_junan_video.paths import AGENT_REF_DIR, OLD_AI_DIR, SCENE_REF_DIR, WORK_DIR

COVER_BOXES = (
    (500, 670, 720, 720),
    (0, 0, 220, 48),
)


def write_agent_plate(source: Path, dest: Path) -> Path:
    """Paint cream over Doubao corner marks and write a JPEG plate."""
    image = Image.open(source).convert("RGB")
    cream = image.getpixel((12, 12))
    if not isinstance(cream, tuple) or len(cream) < 3:
        raise RuntimeError(f"plate must be RGB: {source}")
    fill = (int(cream[0]), int(cream[1]), int(cream[2]))
    draw = ImageDraw.Draw(image)
    for box in COVER_BOXES:
        draw.rectangle(box, fill=fill)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="JPEG", quality=94, optimize=True)
    return dest


def agent_plate_paths() -> tuple[Path, Path]:
    """Return wink and smile plates extracted from the WeChat source."""
    wink = AGENT_REF_DIR / "t0.3.jpg"
    smile = AGENT_REF_DIR / "t1.5.jpg"
    if not wink.is_file() or not smile.is_file():
        raise RuntimeError(f"agent stills missing in {AGENT_REF_DIR}")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    return (
        write_agent_plate(wink, WORK_DIR / "agent-wink.jpg"),
        write_agent_plate(smile, WORK_DIR / "agent-smile.jpg"),
    )


def _ffmpeg_bin() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    conda = Path.home() / "miniconda3" / "envs" / "python313" / "bin" / "ffmpeg"
    if conda.is_file():
        return str(conda)
    raise RuntimeError("ffmpeg not on PATH")


def extract_scene_still(source_name: str, dest_name: str) -> Path:
    """Grab a mid frame from an earlier empty-shot MP4 as the environment lock."""
    source = OLD_AI_DIR / source_name
    if not source.is_file():
        raise RuntimeError(f"environment mp4 missing: {source}")
    dest = SCENE_REF_DIR / dest_name
    if dest.is_file() and dest.stat().st_size > 1000:
        return dest
    SCENE_REF_DIR.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [_ffmpeg_bin(), "-y", "-ss", "2", "-i", str(source), "-frames:v", "1", "-q:v", "3", str(dest)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not dest.is_file():
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "extract failed"
        raise RuntimeError(f"scene still {source_name}: {tail}")
    return dest
