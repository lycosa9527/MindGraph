"""Off-screen narration for the October promo. The roles stay silent."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import requests

from scripts.sync_classroom_video.plates import ffmpeg_bin
from scripts.training_roles.wan_client import synthesize_tts

NARRATOR_VOICE = "longsanshu_v3.1"
LEAD_SECONDS = 0.25
MAX_TEMPO = 1.35
MAX_HOLD = 8.0


def mix_narration(api_key: str, video: Path, speech: str, dest: Path) -> None:
    """Lay the mature male read over foley. Hold the last frame if the line runs long."""
    text = " ".join(speech.split())
    if not text:
        raise ValueError("narration is empty")
    wav = dest.with_suffix(".wav")
    _write_wav(api_key, text, wav)
    tempo, hold = _fit(_duration(video), _duration(wav))
    _mix(video, wav, dest, tempo, hold, _has_audio(video))
    print(f"voice {dest.name} tempo={tempo:.2f} hold={hold:.1f}", flush=True)


def _write_wav(api_key: str, text: str, dest: Path) -> None:
    url = synthesize_tts(api_key, text, NARRATOR_VOICE)
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with requests.get(url, timeout=180) as response:
                response.raise_for_status()
                dest.write_bytes(response.content)
            print(f"voice wav {dest.name} {dest.stat().st_size}", flush=True)
            return
        except requests.RequestException as exc:
            last_error = exc
            print(f"voice download retry {attempt} {type(exc).__name__}", flush=True)
            time.sleep(2 * attempt)
    raise RuntimeError(f"narration download failed: {last_error}")


def _fit(video_seconds: float, voice_seconds: float) -> tuple[float, float]:
    needed = voice_seconds + LEAD_SECONDS
    if needed <= video_seconds:
        return 1.0, 0.0
    hold = min(MAX_HOLD, needed - video_seconds)
    covered = video_seconds + hold - LEAD_SECONDS
    tempo = voice_seconds / covered if covered > 0 else MAX_TEMPO
    if tempo <= 1.0:
        return 1.0, hold
    return min(MAX_TEMPO, tempo), hold


def _mix(video: Path, wav: Path, dest: Path, tempo: float, hold: float, has_audio: bool) -> None:
    delay_ms = int(LEAD_SECONDS * 1000)
    voice = f"atempo={tempo:.3f}," if tempo > 1.01 else ""
    voice_chain = f"[1:a]{voice}volume=1.0,adelay={delay_ms}|{delay_ms}[vo]"
    if has_audio:
        graph = (
            f"[0:v]tpad=stop_mode=clone:stop_duration={hold:.3f}[v];"
            f"[0:a]volume=0.38,apad=pad_dur={hold:.3f}[foley];"
            f"{voice_chain};"
            "[foley][vo]amix=inputs=2:duration=longest:dropout_transition=0[a]"
        )
    else:
        graph = f"[0:v]tpad=stop_mode=clone:stop_duration={hold:.3f}[v];{voice_chain};[vo]anull[a]"
    _run_ffmpeg(
        [
            ffmpeg_bin(),
            "-y",
            "-i",
            str(video),
            "-i",
            str(wav),
            "-filter_complex",
            graph,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(dest),
        ],
        dest.name,
    )


def _run_ffmpeg(args: list[str], label: str) -> None:
    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "ffmpeg failed"
        raise RuntimeError(f"{label}: {tail}")


def _duration(path: Path) -> float:
    completed = subprocess.run(
        [_ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError(f"ffprobe duration failed for {path.name}")
    return float(completed.stdout.strip())


def _has_audio(path: Path) -> bool:
    completed = subprocess.run(
        [
            _ffprobe(),
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return "audio" in completed.stdout


def _ffprobe() -> str:
    found = shutil.which("ffprobe")
    if found:
        return found
    sibling = Path(ffmpeg_bin()).with_name("ffprobe")
    if sibling.is_file():
        return str(sibling)
    raise RuntimeError("ffprobe not on PATH")
