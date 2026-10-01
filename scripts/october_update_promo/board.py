"""Pin a real screenshot onto the green board and pan across it.

Wan leaves the board empty. This pass finds that green region and paints
a moving crop of the screenshot into it, so the roles stay in front.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.sync_classroom_video.plates import ffmpeg_bin

Crop = tuple[float, float, float, float]
Box = tuple[int, int, int, int]


def crop_at(crops: tuple[Crop, ...], progress: float) -> Crop:
    """Interpolate evenly spaced crops. ``progress`` runs from 0 to 1."""
    if len(crops) < 2:
        raise ValueError("a board move needs a start crop and an end crop")
    span = len(crops) - 1
    position = min(1.0, max(0.0, progress)) * span
    index = min(int(position), span - 1)
    local = position - index
    start = crops[index]
    end = crops[index + 1]
    return (
        start[0] + (end[0] - start[0]) * local,
        start[1] + (end[1] - start[1]) * local,
        start[2] + (end[2] - start[2]) * local,
        start[3] + (end[3] - start[3]) * local,
    )


def board_mask(frame: np.ndarray) -> np.ndarray:
    """Largest bright or olive green region that can be the wall board."""
    candidates = _green_pixels(frame)
    height, width = candidates.shape
    step = max(1, width // 160)
    small = _shrink(candidates, step)
    min_cells = max(8, int(0.025 * height * width / (step * step)))
    chosen = _best_component(small, min_cells, 0.78)
    if not chosen.any():
        return np.zeros((height, width), dtype=bool)
    lifted = np.repeat(np.repeat(chosen, step, axis=0), step, axis=1)
    full = np.zeros((height, width), dtype=bool)
    full[: lifted.shape[0], : lifted.shape[1]] = lifted
    return _grow_board(frame, full & candidates)


def _grow_board(frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Spread into the darker green rim without crossing fur, wood, or walls."""
    if not mask.any():
        return mask
    red = frame[:, :, 0].astype(np.int16)
    green = frame[:, :, 1].astype(np.int16)
    blue = frame[:, :, 2].astype(np.int16)
    near = (green > red + 12) & (green > blue + 4) & (red < 160) & (green > 45) & (green < 220)
    grown = mask.copy()
    for _ in range(28):
        expanded = grown.copy()
        expanded[1:, :] |= grown[:-1, :]
        expanded[:-1, :] |= grown[1:, :]
        expanded[:, 1:] |= grown[:, :-1]
        expanded[:, :-1] |= grown[:, 1:]
        grown = grown | (expanded & near)
    return grown


def _shrink(mask: np.ndarray, step: int) -> np.ndarray:
    """True when any pixel in the block is green, so a thin bridge still connects."""
    height, width = mask.shape
    trimmed_h = height - (height % step)
    trimmed_w = width - (width % step)
    if trimmed_h == 0 or trimmed_w == 0:
        return mask
    view = mask[:trimmed_h, :trimmed_w]
    blocks = view.reshape(trimmed_h // step, step, trimmed_w // step, step)
    return blocks.any(axis=(1, 3))


def pin_screenshot(video: Path, image: Path, crops: tuple[Crop, ...], dest: Path) -> None:
    """Paint ``image`` through the green board and keep the clip's foley."""
    if len(crops) < 2:
        raise ValueError(f"{video.name} needs a start crop and an end crop")
    if not image.is_file():
        raise FileNotFoundError(image)
    spec = _video_spec(video)
    total = max(1, int(round(_duration(video) * spec[2])))
    shot = Image.open(image).convert("RGB")
    dest.parent.mkdir(parents=True, exist_ok=True)
    _stream_pin(video, dest, shot, crops, spec, total)
    print(f"board {dest.name}", flush=True)


def _green_pixels(frame: np.ndarray) -> np.ndarray:
    red = frame[:, :, 0].astype(np.int16)
    green = frame[:, :, 1].astype(np.int16)
    blue = frame[:, :, 2].astype(np.int16)
    chroma = (green > 150) & (red < 120) & (blue < 130) & (green > red + 45) & (green > blue + 35)
    olive = (
        (green > 100)
        & (green < 190)
        & (red > 40)
        & (red < 130)
        & (blue > 45)
        & (blue < 145)
        & (green > red + 28)
        & (green > blue + 8)
    )
    return chroma | olive


def _best_component(small: np.ndarray, min_cells: int, max_center: float) -> np.ndarray:
    height, width = small.shape
    seen = np.zeros((height, width), dtype=bool)
    labels = np.zeros((height, width), dtype=np.int32)
    areas = [0]
    centers = [0.0]
    label = 0

    def push(y_pos: int, x_pos: int, stack: list[tuple[int, int]], current: int) -> None:
        if y_pos < 0 or x_pos < 0 or y_pos >= height or x_pos >= width:
            return
        if not small[y_pos, x_pos] or seen[y_pos, x_pos]:
            return
        seen[y_pos, x_pos] = True
        labels[y_pos, x_pos] = current
        stack.append((y_pos, x_pos))

    ys_found, xs_found = np.nonzero(small)
    for start_y, start_x in zip(ys_found.tolist(), xs_found.tolist(), strict=True):
        if seen[start_y, start_x]:
            continue
        label += 1
        areas.append(0)
        centers.append(0.0)
        stack = [(start_y, start_x)]
        seen[start_y, start_x] = True
        labels[start_y, start_x] = label
        while stack:
            y_pos, x_pos = stack.pop()
            areas[label] += 1
            centers[label] += y_pos
            push(y_pos - 1, x_pos, stack, label)
            push(y_pos + 1, x_pos, stack, label)
            push(y_pos, x_pos - 1, stack, label)
            push(y_pos, x_pos + 1, stack, label)
    best = _pick_label(areas, centers, min_cells, height * max_center)
    if best == 0:
        return np.zeros((height, width), dtype=bool)
    return labels == best


def _pick_label(areas: list[int], centers: list[float], min_cells: int, max_y: float) -> int:
    best = 0
    best_area = 0
    for index, area in enumerate(areas):
        if index == 0 or area < min_cells or area <= best_area:
            continue
        if centers[index] / area > max_y:
            continue
        best = index
        best_area = area
    return best


def _bounds(mask: np.ndarray) -> Box | None:
    ys_found, xs_found = np.nonzero(mask)
    if ys_found.size == 0:
        return None
    return int(xs_found.min()), int(ys_found.min()), int(xs_found.max()) + 1, int(ys_found.max()) + 1


def _blend_box(previous: Box | None, box: Box) -> Box:
    if previous is None:
        return box
    return (
        int(round(previous[0] * 0.55 + box[0] * 0.45)),
        int(round(previous[1] * 0.55 + box[1] * 0.45)),
        int(round(previous[2] * 0.55 + box[2] * 0.45)),
        int(round(previous[3] * 0.55 + box[3] * 0.45)),
    )


def _clip_box(box: Box, width: int, height: int) -> Box | None:
    left, top, right, bottom = box
    left = min(max(0, left), width - 1)
    top = min(max(0, top), height - 1)
    right = min(max(left + 1, right), width)
    bottom = min(max(top + 1, bottom), height)
    if right - left < 8 or bottom - top < 8:
        return None
    return left, top, right, bottom


def _source_window(shot: Image.Image, crop: Crop) -> Image.Image:
    width, height = shot.size
    left = min(width - 1, max(0, int(crop[0] * width)))
    top = min(height - 1, max(0, int(crop[1] * height)))
    right = min(width, max(left + 1, int((crop[0] + crop[2]) * width)))
    bottom = min(height, max(top + 1, int((crop[1] + crop[3]) * height)))
    return shot.crop((left, top, right, bottom))


def _paint(frame: np.ndarray, shot: Image.Image, crop: Crop, mask: np.ndarray, box: Box) -> None:
    clipped = _clip_box(box, frame.shape[1], frame.shape[0])
    if clipped is None:
        return
    left, top, right, bottom = clipped
    resized = np.asarray(_source_window(shot, crop).resize((right - left, bottom - top), Image.Resampling.BILINEAR))
    region = mask[top:bottom, left:right]
    if resized.shape[0] != region.shape[0] or resized.shape[1] != region.shape[1]:
        return
    frame[top:bottom, left:right][region] = resized[region]


def _video_spec(video: Path) -> tuple[int, int, float]:
    probe = _ffprobe()
    completed = subprocess.run(
        [
            probe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate",
            "-of",
            "csv=p=0",
            str(video),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {video.name}")
    width_text, height_text, rate_text = completed.stdout.strip().split(",")
    return int(width_text), int(height_text), _frame_rate(rate_text)


def _frame_rate(rate_text: str) -> float:
    if "/" in rate_text:
        num_text, den_text = rate_text.split("/", 1)
        denom = float(den_text)
        if denom == 0:
            return 30.0
        return float(num_text) / denom
    return float(rate_text)


def _ffprobe() -> str:
    found = shutil.which("ffprobe")
    if found:
        return found
    sibling = Path(ffmpeg_bin()).with_name("ffprobe")
    if sibling.is_file():
        return str(sibling)
    raise RuntimeError("ffprobe not on PATH")


def _stream_pin(
    video: Path,
    dest: Path,
    shot: Image.Image,
    crops: tuple[Crop, ...],
    spec: tuple[int, int, float],
    total: int,
) -> None:
    width, height, rate = spec
    frame_bytes = width * height * 3
    index = 0
    box: Box | None = None
    with (
        subprocess.Popen(_decoder_cmd(video), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as decoder,
        subprocess.Popen(
            _encoder_cmd(dest, width, height, rate, video),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        ) as encoder,
    ):
        assert decoder.stdout is not None
        assert encoder.stdin is not None
        while True:
            raw = decoder.stdout.read(frame_bytes)
            if len(raw) < frame_bytes:
                break
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3)).copy()
            box = _paint_frame(frame, shot, crops, box, index, total)
            encoder.stdin.write(frame.tobytes())
            index += 1
            if index == 1 or index % 48 == 0:
                print(f"board {dest.name} frame {index}", flush=True)
        _close_pipes(decoder, encoder, dest, index)


def _decoder_cmd(video: Path) -> list[str]:
    return [ffmpeg_bin(), "-v", "error", "-i", str(video), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]


def _encoder_cmd(dest: Path, width: int, height: int, rate: float, video: Path) -> list[str]:
    return [
        ffmpeg_bin(),
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{rate:.4f}",
        "-i",
        "-",
        "-i",
        str(video),
        "-map",
        "0:v",
        "-map",
        "1:a?",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        str(dest),
    ]


def _paint_frame(
    frame: np.ndarray,
    shot: Image.Image,
    crops: tuple[Crop, ...],
    box: Box | None,
    index: int,
    total: int,
) -> Box | None:
    mask = board_mask(frame)
    found = _bounds(mask)
    if found is None:
        return box
    box = _blend_box(box, found)
    progress = 0.0 if total <= 1 else min(1.0, index / (total - 1))
    _paint(frame, shot, crop_at(crops, progress), mask, box)
    return box


def _duration(video: Path) -> float:
    completed = subprocess.run(
        [_ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError(f"ffprobe duration failed for {video.name}")
    return float(completed.stdout.strip())


def _close_pipes(
    decoder: subprocess.Popen[bytes],
    encoder: subprocess.Popen[bytes],
    dest: Path,
    frames: int,
) -> None:
    if encoder.stdin is not None:
        encoder.stdin.close()
    decoder.wait(timeout=60)
    error = encoder.stderr.read().decode("utf-8", errors="replace") if encoder.stderr is not None else ""
    code = encoder.wait(timeout=120)
    if frames == 0 or code != 0:
        raise RuntimeError(f"board pin failed for {dest.name}: {error.strip() or code}")
