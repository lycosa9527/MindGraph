"""Export office-battle scenes without greenscreen keying.

Scene WebPs keep the 16:9 frame. WeChat custom emoji is 240x240 1:1,
center-cropped so the set does not get empty letterbox bars.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PIL import Image

from scripts.training_roles.export import (
    WECHAT_MAX_BYTES,
    WECHAT_SIZE,
    patch_webp_dispose,
    scale_width,
)
from scripts.cat_office_battles.catalog import BattleZone
from scripts.cat_office_battles.paths import WORK_DIR


def clip_stem(zone: BattleZone) -> str:
    """Desktop filename stem, e.g. 01-desk-stare_工位区·背后灵凝视."""
    return f"{zone['id']}-{zone['slug']}_{zone['name']}"


def center_crop_square(image: Image.Image) -> Image.Image:
    """Crop the center square from a landscape scene frame."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return rgb.crop((left, top, left + side, top + side))


def wechat_square(image: Image.Image, size: int = WECHAT_SIZE) -> Image.Image:
    """1:1 WeChat emoji frame at 240x240."""
    return center_crop_square(image).resize((size, size), Image.Resampling.LANCZOS)


def _pick_frames(frames: list[Image.Image], count: int) -> list[Image.Image]:
    if count >= len(frames) or count <= 1:
        return frames[: max(1, count)]
    last = len(frames) - 1
    indexes = [round(index * last / (count - 1)) for index in range(count)]
    return [frames[index] for index in indexes]


def load_still_frames(folder: Path) -> list[Image.Image]:
    """Load 01.png, 02.png, … in order."""
    paths = sorted(folder.glob("*.png"))
    if not paths:
        raise RuntimeError(f"no stills in {folder}")
    return [Image.open(path).convert("RGB") for path in paths]


def _ffmpeg_bin() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    bundled = Path.home() / "miniconda3" / "lib" / "python3.13" / "site-packages" / "imageio_ffmpeg" / "binaries"
    matches = sorted(bundled.glob("ffmpeg*"))
    if matches:
        return str(matches[0])
    raise RuntimeError("ffmpeg not on PATH")


def extract_scene_frames(mp4: Path) -> list[Image.Image]:
    """Decode 12 fps RGB frames. Do not chroma-key office scenes."""
    frames_dir = WORK_DIR / "frames" / mp4.stem
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("*.png"):
        old.unlink()
    cmd = [
        _ffmpeg_bin(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(mp4),
        "-vf",
        "fps=12",
        str(frames_dir / "frame-%03d.png"),
    ]
    code = os.spawnvp(os.P_WAIT, cmd[0], cmd)
    if code != 0:
        raise RuntimeError(f"ffmpeg extract failed {mp4.name}")
    return [Image.open(path).convert("RGB") for path in sorted(frames_dir.glob("frame-*.png"))]


def save_scene_webp(frames: list[Image.Image], dest: Path, width: int = 720) -> None:
    """Write a 16:9 looping scene WebP."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    scaled = scale_width([frame.convert("RGBA") for frame in frames], width)
    scaled[0].save(
        dest,
        format="WEBP",
        save_all=True,
        append_images=scaled[1:],
        loop=0,
        duration=200 if len(scaled) <= 8 else 83,
        lossless=False,
        quality=72,
        method=4,
        background=(0, 0, 0, 0),
    )
    patch_webp_dispose(dest)
    print(f"webp {dest.name} {dest.stat().st_size} {scaled[0].size}", flush=True)


def save_wechat_gif(frames: list[Image.Image], dest: Path) -> None:
    """Write an opaque 240x240 1:1 GIF under 500KB."""
    squared = [wechat_square(frame) for frame in frames]
    last_size = 0
    for count, colors in ((24, 128), (20, 96), (16, 96), (12, 64), (8, 48)):
        picked = _pick_frames(squared, min(count, len(squared)))
        duration = max(80, round(4000 / len(picked)))
        indexed = []
        for frame in picked:
            pal = frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)
            indexed.append(pal)
        dest.parent.mkdir(parents=True, exist_ok=True)
        indexed[0].save(
            dest,
            save_all=True,
            append_images=indexed[1:],
            loop=0,
            duration=duration,
            disposal=2,
            optimize=True,
        )
        last_size = dest.stat().st_size
        if last_size <= WECHAT_MAX_BYTES:
            print(f"wechat {dest.name} {last_size} 240x240", flush=True)
            return
    raise RuntimeError(f"{dest.name} still {last_size} after tightest pass")


def export_scene_bundle(
    frames: list[Image.Image],
    zone: BattleZone,
    dest_dir: Path,
    *,
    webp_width: int = 720,
) -> None:
    """Write scene WebP plus 1:1 WeChat GIF for one zone."""
    stem = clip_stem(zone)
    wechat_dir = dest_dir / "wechat-emoji"
    save_scene_webp(frames, dest_dir / f"{stem}.webp", width=webp_width)
    save_wechat_gif(frames, wechat_dir / f"{stem}.gif")


def export_video_bundle(mp4: Path, zone: BattleZone, dest_dir: Path) -> None:
    """Export an HD scene MP4 to 1080-wide WebP and 240x240 WeChat GIF."""
    frames = extract_scene_frames(mp4)
    export_scene_bundle(frames, zone, dest_dir, webp_width=1920)
