"""Chroma-key Wan MP4s to transparent WebP / WeChat GIF / public assets."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.training_roles.catalog import RoleAction, role_clip_id
from scripts.training_roles.paths import PUBLIC_ROLES_DIR, WORK_DIR

SHIP_WIDTH = 320
THUMB_WIDTH = 96
WORK_WIDTH = 480
WECHAT_SIZE = 240
WECHAT_MAX_BYTES = 490_000


def ffmpeg_bin() -> str:
    """Use system ffmpeg; do not hide the import inside a function."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError("ffmpeg not on PATH")


_RIM = 8
_FRINGE_STEPS = 2


def _screen_pixels(red: np.ndarray, green: np.ndarray, blue: np.ndarray) -> np.ndarray:
    """Bright screen plus the darker green floor that still touches it."""
    greenness = green - np.maximum(red, blue)
    bright = (green > 90) & (greenness > 28) & (green > red + 20) & (green > blue + 20)
    floor = (green > 40) & (greenness > 32) & (green > red + 16) & (green > blue + 16)
    return bright | floor


def _fringe_pixels(red: np.ndarray, green: np.ndarray, blue: np.ndarray) -> np.ndarray:
    """Softer green halo that only counts when it touches the screen."""
    greenness = green - np.maximum(red, blue)
    return (green > 70) & (greenness > 14) & (green > red + 10) & (green > blue + 10)


def _row_runs(row: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    padded = np.zeros(row.size + 2, dtype=np.int8)
    padded[1:-1] = row.astype(np.int8)
    changes = np.diff(padded)
    return np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)


def _find_run(parent: list[int], run_id: int) -> int:
    while parent[run_id] != run_id:
        parent[run_id] = parent[parent[run_id]]
        run_id = parent[run_id]
    return run_id


def _join_runs(parent: list[int], left: int, right: int) -> None:
    left_root = _find_run(parent, left)
    right_root = _find_run(parent, right)
    if left_root != right_root:
        parent[right_root] = left_root


def _link_vertical(
    parent: list[int],
    previous: list[tuple[int, int, int]],
    current: list[tuple[int, int, int]],
) -> None:
    """Join runs that share a column with the row above."""
    prev_index = 0
    curr_index = 0
    while prev_index < len(previous) and curr_index < len(current):
        prev_start, prev_end, prev_id = previous[prev_index]
        start, end, run_id = current[curr_index]
        if prev_end <= start:
            prev_index += 1
        elif end <= prev_start:
            curr_index += 1
        else:
            _join_runs(parent, prev_id, run_id)
            if prev_end < end:
                prev_index += 1
            else:
                curr_index += 1


def _rim_seed(chroma: np.ndarray) -> np.ndarray:
    seed = np.zeros(chroma.shape, dtype=bool)
    seed[:_RIM, :] = True
    seed[-_RIM:, :] = True
    seed[:, :_RIM] = True
    seed[:, -_RIM:] = True
    return seed


def _connected(chroma: np.ndarray, seed: np.ndarray) -> np.ndarray:
    """Chroma runs that touch seed, following the screen around the subjects."""
    parent: list[int] = []
    seeds: list[int] = []
    rows: list[list[tuple[int, int, int]]] = []
    for row_index in range(chroma.shape[0]):
        starts, ends = _row_runs(chroma[row_index])
        current: list[tuple[int, int, int]] = []
        seed_row = seed[row_index]
        for start, end in zip(starts.tolist(), ends.tolist(), strict=True):
            run_id = len(parent)
            parent.append(run_id)
            if bool(seed_row[start:end].any()):
                seeds.append(run_id)
            current.append((start, end, run_id))
        if rows:
            _link_vertical(parent, rows[-1], current)
        rows.append(current)
    background_roots = {_find_run(parent, run_id) for run_id in seeds}
    mask = np.zeros(chroma.shape, dtype=bool)
    for row_index, current in enumerate(rows):
        for start, end, run_id in current:
            if _find_run(parent, run_id) in background_roots:
                mask[row_index, start:end] = True
    return mask


def _edge_screen(chroma: np.ndarray) -> np.ndarray:
    """Screen green that reaches the frame rim. Green shut inside a prop stays."""
    return _connected(chroma, _rim_seed(chroma))


def _component_rows(
    mask: np.ndarray,
) -> tuple[list[int], list[list[tuple[int, int, int]]]]:
    parent: list[int] = []
    rows: list[list[tuple[int, int, int]]] = []
    for row_index in range(mask.shape[0]):
        starts, ends = _row_runs(mask[row_index])
        current: list[tuple[int, int, int]] = []
        for start, end in zip(starts.tolist(), ends.tolist(), strict=True):
            run_id = len(parent)
            parent.append(run_id)
            current.append((start, end, run_id))
        if rows:
            _link_vertical(parent, rows[-1], current)
        rows.append(current)
    return parent, rows


def _island_limit(width: int) -> int:
    """A backdrop shut behind a prop. Smaller than this can still be a button."""
    return max(500, int(4000 * (width / 1080) ** 2))


def _hue_limit(width: int) -> int:
    """Screen-colored gaps. A shaded button sits below this and keeps its green."""
    return max(200, int(1400 * (width / 1080) ** 2))


def _enclosed_screen(
    chroma: np.ndarray,
    red: np.ndarray,
    green: np.ndarray,
    blue: np.ndarray,
    width: int,
) -> np.ndarray:
    """Drop big enclosed backdrops, and smaller patches that still match the screen."""
    parent, rows = _component_rows(chroma)
    sizes: dict[int, int] = {}
    sums: dict[int, np.ndarray] = {}
    for row_index, current in enumerate(rows):
        for start, end, run_id in current:
            root = _find_run(parent, run_id)
            sizes[root] = sizes.get(root, 0) + (end - start)
            block = np.stack(
                (red[row_index, start:end], green[row_index, start:end], blue[row_index, start:end]),
                axis=1,
            )
            sums[root] = block.sum(axis=0) if root not in sums else sums[root] + block.sum(axis=0)
    big = _island_limit(width)
    hue_n = _hue_limit(width)
    drop: set[int] = set()
    for root, size in sizes.items():
        if size >= big:
            drop.add(root)
            continue
        if size < hue_n:
            continue
        mean = sums[root] / size
        screen_hued = mean[1] >= 158 and mean[0] < 95 and mean[2] < 95
        if screen_hued:
            drop.add(root)
    islands = np.zeros(chroma.shape, dtype=bool)
    for row_index, current in enumerate(rows):
        for start, end, run_id in current:
            if _find_run(parent, run_id) in drop:
                islands[row_index, start:end] = True
    return islands


def _dilate(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, constant_values=False)
    center = padded[1:-1, 1:-1]
    return center | padded[:-2, 1:-1] | padded[2:, 1:-1] | padded[1:-1, :-2] | padded[1:-1, 2:]


def _grow_fringe(background: np.ndarray, fringe: np.ndarray) -> np.ndarray:
    grown = background
    allowed = fringe | background
    for _ in range(_FRINGE_STEPS):
        grown = _dilate(grown) & allowed
    return grown


def key_green(image: Image.Image) -> Image.Image:
    """Trace the green screen from the frame edge and leave interior green in place."""
    rgba = np.asarray(image.convert("RGBA")).astype(np.float32)
    red, green, blue = rgba[:, :, 0], rgba[:, :, 1], rgba[:, :, 2]
    chroma = _screen_pixels(red, green, blue)
    screen = _edge_screen(chroma)
    enclosed = _enclosed_screen(chroma & ~screen, red, green, blue, rgba.shape[1])
    background = _grow_fringe(screen | enclosed, _fringe_pixels(red, green, blue))
    greenness = green - np.maximum(red, blue)
    # Modest green on cloth is spill. A saturated logo stays green.
    spill = (~background) & (greenness > 6) & (greenness < 48)
    rgba[:, :, 1] = np.where(spill, np.minimum(green, np.maximum(red, blue)), green)
    rgba[:, :, 3] = np.where(background, 0.0, 255.0)
    return Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")


def crop_union(frames: list[Image.Image], pad: int = 48) -> list[Image.Image]:
    """Crop to the union alpha box so the cat stays fully in frame."""
    union = None
    for frame in frames:
        alpha = np.asarray(frame.split()[-1]) > 8
        union = alpha if union is None else union | alpha
    if union is None or not union.any():
        return frames
    rows = np.any(union, axis=1)
    cols = np.any(union, axis=0)
    top = max(0, int(np.argmax(rows)) - pad)
    bottom = min(frames[0].height, int(len(rows) - np.argmax(rows[::-1])) + pad)
    left = max(0, int(np.argmax(cols)) - pad)
    right = min(frames[0].width, int(len(cols) - np.argmax(cols[::-1])) + pad)
    return [frame.crop((left, top, right, bottom)) for frame in frames]


def scale_width(frames: list[Image.Image], width: int) -> list[Image.Image]:
    """Scale every frame to a max width, keeping aspect."""
    if not frames or frames[0].width <= width:
        return frames
    height = max(1, int(frames[0].height * (width / frames[0].width)))
    return [frame.resize((width, height), Image.Resampling.LANCZOS) for frame in frames]


def patch_webp_dispose(path: Path) -> None:
    """Force ANMF dispose=background + no-blend so leftover frames do not ghost."""
    data = bytearray(path.read_bytes())
    if data[0:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise RuntimeError(f"not webp: {path}")
    index = 12
    patched = 0
    while index + 8 <= len(data):
        tag = bytes(data[index : index + 4])
        size = int.from_bytes(data[index + 4 : index + 8], "little")
        payload = index + 8
        if tag == b"ANMF" and size >= 16:
            data[payload + 15] = (data[payload + 15] & ~0x03) | 0x03
            patched += 1
        index = payload + size + (size & 1)
    path.write_bytes(data)
    print(f"webp dispose patched frames={patched}", flush=True)


def save_webp(frames: list[Image.Image], dest: Path, *, lossless: bool) -> None:
    """Write an animated WebP and patch dispose flags."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        dest,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=83,
        lossless=lossless,
        exact=True,
        quality=72 if not lossless else 80,
        method=4 if not lossless else 6,
        kmin=0,
        kmax=1,
        background=(0, 0, 0, 0),
    )
    patch_webp_dispose(dest)
    print(f"webp {dest.name} {dest.stat().st_size} {frames[0].size}", flush=True)


def extract_keyed_frames(
    mp4: Path,
    frames_dir: Path | None = None,
) -> list[Image.Image]:
    """Decode 12 fps PNG frames and key the green screen."""
    target = frames_dir or (WORK_DIR / "frames" / mp4.stem)
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("*.png"):
        old.unlink()
    cmd = [
        ffmpeg_bin(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(mp4),
        "-vf",
        "fps=12",
        str(target / "frame-%03d.png"),
    ]
    code = os.spawnvp(os.P_WAIT, cmd[0], cmd)
    if code != 0:
        raise RuntimeError(f"ffmpeg extract failed {mp4.name}")
    keyed = [key_green(Image.open(path)) for path in sorted(target.glob("frame-*.png"))]
    return crop_union(keyed, pad=48)


def ship_public_webps(frames: list[Image.Image], clip_id: str) -> None:
    """Write the Course Builder on-demand anim + thumb under public/."""
    PUBLIC_ROLES_DIR.mkdir(parents=True, exist_ok=True)
    shipped = scale_width(frames, SHIP_WIDTH)
    save_webp(shipped, PUBLIC_ROLES_DIR / f"{clip_id}.webp", lossless=False)
    thumb = scale_width([shipped[0]], THUMB_WIDTH)[0]
    dest = PUBLIC_ROLES_DIR / f"{clip_id}-thumb.webp"
    thumb.save(dest, format="WEBP", lossless=False, exact=True, quality=78, method=4)
    print(f"thumb {dest.name} {dest.stat().st_size}", flush=True)


def export_mp4(mp4: Path, action: RoleAction) -> None:
    """Key one clip and ship the public WebPs used by Course Builder."""
    frames = extract_keyed_frames(mp4)
    work = scale_width(frames, WORK_WIDTH)
    work_webp = WORK_DIR / f"{role_clip_id(action)}.webp"
    save_webp(work, work_webp, lossless=True)
    ship_public_webps(frames, role_clip_id(action))


def _fit_square(image: Image.Image, size: int = WECHAT_SIZE) -> Image.Image:
    rgba = image.convert("RGBA")
    ratio = min(size / rgba.width, size / rgba.height)
    new_w = max(1, int(rgba.width * ratio))
    new_h = max(1, int(rgba.height * ratio))
    resized = rgba.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(resized, ((size - new_w) // 2, (size - new_h) // 2), resized)
    return canvas


def _pick_frames(frames: list[Image.Image], count: int) -> list[Image.Image]:
    if count >= len(frames) or count <= 1:
        return frames[: max(1, count)]
    last = len(frames) - 1
    indexes = [round(index * last / (count - 1)) for index in range(count)]
    return [frames[index] for index in indexes]


def export_wechat_gif(
    mp4: Path,
    dest: Path,
    frames_dir: Path | None = None,
) -> None:
    """240x240 GIF under 500KB for WeChat custom emoji."""
    keyed = crop_union(extract_keyed_frames(mp4, frames_dir), pad=24)
    squared = [_fit_square(frame) for frame in keyed]
    last_size = 0
    for count, colors in ((24, 128), (20, 96), (16, 96), (12, 64), (8, 48)):
        picked = _pick_frames(squared, count)
        duration = max(80, round(5000 / len(picked)))
        indexed = []
        for frame in picked:
            rgba = frame.convert("RGBA")
            alpha = rgba.getchannel("A")
            pal = rgba.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)
            mask = Image.eval(alpha, lambda a: 255 if a <= 16 else 0)
            pal.paste(255, mask)
            pal.info["transparency"] = 255
            indexed.append(pal)
        dest.parent.mkdir(parents=True, exist_ok=True)
        indexed[0].save(
            dest,
            save_all=True,
            append_images=indexed[1:],
            loop=0,
            duration=duration,
            disposal=2,
            transparency=255,
            optimize=True,
        )
        last_size = dest.stat().st_size
        if last_size <= WECHAT_MAX_BYTES:
            print(f"wechat {dest.name} {last_size}", flush=True)
            return
    raise RuntimeError(f"{dest.name} still {last_size} after tightest pass")
