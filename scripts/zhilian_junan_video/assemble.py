"""Stitch the walking tour: a still pushes in, then dissolves into each spoken clip."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from scripts.zhilian_junan_video.activities import activity_source_for_filename
from scripts.zhilian_junan_video.paths import DESKTOP_DIR, MATERIALS_DIR
from scripts.zhilian_junan_video.plates import ffmpeg_bin

CLIP_DIR = MATERIALS_DIR / "v1"
CUT_DIR = DESKTOP_DIR / "成片"
OPENING = "01-开篇.mp4"
CLOSING = "19-收束.mp4"
PHOTO_LEAD = 7.0
INNER_FADE = 0.45
JOIN_FADE = 0.35
TAIL_PAD = 0.4
FRAME_W = 1920
FRAME_H = 1080
FRAME_SIZE = f"{FRAME_W}:{FRAME_H}"
# zoompan snaps x/y to whole pixels. Working 4x larger keeps that snap under a quarter pixel.
PHOTO_ZOOM = 1.06
PHOTO_SCALE = 4

# Spine from the screen script, about two and a half minutes.
MAIN_CUT: tuple[str, ...] = (
    OPENING,
    "02-版画.mp4",
    "03-泥塑.mp4",
    "04-科创.mp4",
    "06-实验.mp4",
    "07-研讨.mp4",
    "08-未来学习中心.mp4",
    "09-老师在学.mp4",
    "13-武术.mp4",
    "14-跳绳.mp4",
    "17-机器人.mp4",
    CLOSING,
)

# Every finished clip, parked where the script says it can sit. About four minutes.
FULL_CUT: tuple[str, ...] = (
    OPENING,
    "02-版画.mp4",
    "03-泥塑.mp4",
    "04-科创.mp4",
    "05-小龙厨房.mp4",
    "06-实验.mp4",
    "07-研讨.mp4",
    "08-未来学习中心.mp4",
    "09-老师在学.mp4",
    "10-未来名师.mp4",
    "11-跨学段.mp4",
    "12-团辅.mp4",
    "13-武术.mp4",
    "14-跳绳.mp4",
    "15-女篮.mp4",
    "16-药王谷.mp4",
    "17-机器人.mp4",
    "18-粤剧.mp4",
    CLOSING,
)


def _run(args: list[str]) -> None:
    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "ffmpeg failed"
        raise RuntimeError(tail)


def _duration(path: Path) -> float:
    completed = subprocess.run(
        [ffmpeg_bin(), "-i", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    match = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", completed.stderr)
    if match is None:
        raise RuntimeError(f"no duration: {path.name}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _encode_args() -> list[str]:
    return [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        "44100",
    ]


def _still_path(filename: str) -> Path | None:
    if filename in {OPENING, CLOSING}:
        return None
    relative = activity_source_for_filename(filename)
    path = MATERIALS_DIR / relative
    if not path.is_file():
        raise RuntimeError(f"still missing: {relative}")
    return path


def _normalize(source: Path, dest: Path) -> None:
    _run(
        [
            ffmpeg_bin(),
            "-y",
            "-i",
            str(source),
            "-vf",
            f"scale={FRAME_SIZE}:force_original_aspect_ratio=increase,crop={FRAME_SIZE},fps=30,format=yuv420p",
            "-af",
            "aresample=44100,aformat=channel_layouts=stereo",
            *_encode_args(),
            str(dest),
        ]
    )


def _photo_lead(still: Path, dest: Path) -> None:
    frames = int(PHOTO_LEAD * 30)
    wide = FRAME_W * PHOTO_SCALE
    high = FRAME_H * PHOTO_SCALE
    zoom = f"1+{(PHOTO_ZOOM - 1):.4f}*on/{frames - 1}"
    _run(
        [
            ffmpeg_bin(),
            "-y",
            "-i",
            str(still),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-filter_complex",
            (
                f"[0:v]scale={wide}:{high}:force_original_aspect_ratio=increase,crop={wide}:{high},"
                f"zoompan=z='{zoom}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':"
                f"d={frames}:s={FRAME_W}x{FRAME_H}:fps=30,format=yuv420p[v]"
            ),
            "-map",
            "[v]",
            "-map",
            "1:a",
            "-frames:v",
            str(frames),
            *_encode_args(),
            str(dest),
        ]
    )


def _dissolve_still_into_clip(photo: Path, clip: Path, dest: Path) -> None:
    offset = PHOTO_LEAD - INNER_FADE
    _run(
        [
            ffmpeg_bin(),
            "-y",
            "-i",
            str(photo),
            "-i",
            str(clip),
            "-filter_complex",
            (
                f"[0:v][1:v]xfade=transition=fade:duration={INNER_FADE}:offset={offset:.2f},format=yuv420p[v];"
                f"[0:a]atrim=0:{offset:.2f},asetpts=PTS-STARTPTS[head];"
                "[head][1:a]concat=n=2:v=0:a=1[a]"
            ),
            "-map",
            "[v]",
            "-map",
            "[a]",
            *_encode_args(),
            str(dest),
        ]
    )


def _pad_tail(source: Path, dest: Path) -> None:
    _run(
        [
            ffmpeg_bin(),
            "-y",
            "-i",
            str(source),
            "-vf",
            f"tpad=stop_mode=clone:stop_duration={TAIL_PAD},format=yuv420p",
            "-af",
            f"apad=pad_dur={TAIL_PAD}",
            *_encode_args(),
            str(dest),
        ]
    )


def _pad_head(source: Path, dest: Path) -> None:
    delay = int(TAIL_PAD * 1000)
    _run(
        [
            ffmpeg_bin(),
            "-y",
            "-i",
            str(source),
            "-vf",
            f"tpad=start_mode=clone:start_duration={TAIL_PAD},format=yuv420p",
            "-af",
            f"adelay={delay}|{delay}",
            *_encode_args(),
            str(dest),
        ]
    )


def _activity_segment(filename: str, work: Path) -> Path:
    still = _still_path(filename)
    if still is None:
        raise RuntimeError(f"{filename} is a bookend")
    stem = Path(filename).stem
    dest = work / f"{stem}.mp4"
    if dest.is_file() and dest.stat().st_size > 10000:
        return dest
    clip = work / f"{stem}-clip.mp4"
    photo = work / f"{stem}-photo.mp4"
    mixed = work / f"{stem}-mix.mp4"
    _normalize(CLIP_DIR / filename, clip)
    _photo_lead(still, photo)
    _dissolve_still_into_clip(photo, clip, mixed)
    _pad_tail(mixed, dest)
    return dest


def _bookend_segment(filename: str, work: Path) -> Path:
    stem = Path(filename).stem
    dest = work / f"{stem}.mp4"
    if dest.is_file() and dest.stat().st_size > 10000:
        return dest
    normal = work / f"{stem}-clip.mp4"
    _normalize(CLIP_DIR / filename, normal)
    if filename == CLOSING:
        _pad_head(normal, dest)
        return dest
    _pad_tail(normal, dest)
    return dest


def _segment(filename: str, work: Path) -> Path:
    source = CLIP_DIR / filename
    if not source.is_file():
        raise RuntimeError(f"clip missing: {source}")
    if filename in {OPENING, CLOSING}:
        return _bookend_segment(filename, work)
    return _activity_segment(filename, work)


def _join(segments: list[Path], dest: Path) -> None:
    if len(segments) < 2:
        raise RuntimeError("need at least two segments")
    durations = [_duration(path) for path in segments]
    video_filters: list[str] = []
    audio_filters: list[str] = []
    offset = durations[0] - JOIN_FADE
    video_filters.append(f"[0:v][1:v]xfade=transition=fade:duration={JOIN_FADE}:offset={offset:.3f}[v1]")
    audio_filters.append(f"[0:a][1:a]acrossfade=d={JOIN_FADE}:c1=tri:c2=tri[a1]")
    for index in range(2, len(segments)):
        offset += durations[index - 1] - JOIN_FADE
        video_filters.append(
            f"[v{index - 1}][{index}:v]xfade=transition=fade:duration={JOIN_FADE}:offset={offset:.3f}[v{index}]"
        )
        audio_filters.append(f"[a{index - 1}][{index}:a]acrossfade=d={JOIN_FADE}:c1=tri:c2=tri[a{index}]")
    last = len(segments) - 1
    args = [ffmpeg_bin(), "-y"]
    for path in segments:
        args.extend(["-i", str(path)])
    args.extend(
        [
            "-filter_complex",
            ";".join(video_filters + audio_filters),
            "-map",
            f"[v{last}]",
            "-map",
            f"[a{last}]",
            *_encode_args(),
            str(dest),
        ]
    )
    _run(args)


def render_cut(names: tuple[str, ...], dest: Path) -> Path:
    """Build one film. Each activity still pushes for 7s, then dissolves into the spoken clip."""
    work = CUT_DIR / ".segments"
    work.mkdir(parents=True, exist_ok=True)
    segments = [_segment(name, work) for name in names]
    dest.parent.mkdir(parents=True, exist_ok=True)
    _join(segments, dest)
    print(f"cut {dest}", flush=True)
    return dest


def _mirror(path: Path) -> None:
    copied = CLIP_DIR / path.name
    shutil.copy2(path, copied)
    print(f"materials {copied}", flush=True)


def main() -> None:
    """Write the script spine and the longer pick reel."""
    spine = render_cut(MAIN_CUT, CUT_DIR / "主路.mp4")
    pick = render_cut(FULL_CUT, CUT_DIR / "全片-用来挑.mp4")
    _mirror(spine)
    _mirror(pick)


if __name__ == "__main__":
    main()
