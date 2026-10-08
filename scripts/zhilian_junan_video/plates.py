"""Clean Doubao watermarks and pull environment stills for Wan 3.0."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.zhilian_junan_video.paths import (
    AGENT_REF_DIR,
    AGENT_SOURCE,
    OLD_AI_DIR,
    SCENE_REF_DIR,
    WORK_DIR,
)

ACTIVITY_EDGE = 1280

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


def write_plain_plate(dest: Path) -> Path:
    """Cream empty wall used as figure 3 for the opening and closing shots."""
    image = Image.new("RGB", (1280, 720), (244, 236, 220))
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="JPEG", quality=90, optimize=True)
    return dest


def write_activity_plate(source: Path, dest: Path) -> Path:
    """Shrink a client activity photo to a JPEG Wan can take as figure 3."""
    opened = Image.open(source)
    if "A" in opened.getbands():
        rgba = opened.convert("RGBA")
        base = Image.new("RGB", rgba.size, (255, 255, 255))
        base.paste(rgba, mask=rgba.getchannel("A"))
        image = base
    else:
        image = opened.convert("RGB")
    image.thumbnail((ACTIVITY_EDGE, ACTIVITY_EDGE), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="JPEG", quality=86, optimize=True)
    return dest


def agent_plate_paths() -> tuple[Path, Path]:
    """Return wink and smile plates extracted from the WeChat source."""
    ensure_agent_stills()
    wink = AGENT_REF_DIR / "t0.3.jpg"
    smile = AGENT_REF_DIR / "t1.5.jpg"
    if not wink.is_file() or not smile.is_file():
        raise RuntimeError(f"agent stills missing in {AGENT_REF_DIR}")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    return (
        write_agent_plate(wink, WORK_DIR / "agent-wink.jpg"),
        write_agent_plate(smile, WORK_DIR / "agent-smile.jpg"),
    )


def _imageio_ffmpeg() -> str:
    root = Path.home() / "miniconda3" / "envs"
    if not root.is_dir():
        return ""
    matches = sorted(root.glob("*/lib/python*/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux*"))
    if not matches:
        return ""
    return str(matches[-1])


def ffmpeg_bin() -> str:
    """ffmpeg from PATH, the conda env, or the imageio wheel."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    conda = Path.home() / "miniconda3" / "envs" / "python313" / "bin" / "ffmpeg"
    if conda.is_file():
        return str(conda)
    bundled = _imageio_ffmpeg()
    if bundled:
        return bundled
    raise RuntimeError("ffmpeg not on PATH")


def _extract_frame(stamp: str, dest: Path) -> None:
    completed = subprocess.run(
        [
            ffmpeg_bin(),
            "-y",
            "-ss",
            stamp,
            "-i",
            str(AGENT_SOURCE),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(dest),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not dest.is_file():
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "extract failed"
        raise RuntimeError(f"mascot still {stamp}: {tail}")


def ensure_agent_stills() -> None:
    """Pull wink and smile frames from the WeChat mascot clip when plates are missing."""
    wink = AGENT_REF_DIR / "t0.3.jpg"
    smile = AGENT_REF_DIR / "t1.5.jpg"
    ready = wink.is_file() and smile.is_file() and wink.stat().st_size > 1000 and smile.stat().st_size > 1000
    if ready:
        return
    if not AGENT_SOURCE.is_file():
        raise RuntimeError(f"mascot source missing: {AGENT_SOURCE.name}")
    AGENT_REF_DIR.mkdir(parents=True, exist_ok=True)
    _extract_frame("0.3", wink)
    _extract_frame("1.5", smile)


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
        [ffmpeg_bin(), "-y", "-ss", "2", "-i", str(source), "-frames:v", "1", "-q:v", "3", str(dest)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not dest.is_file():
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "extract failed"
        raise RuntimeError(f"scene still {source_name}: {tail}")
    return dest
