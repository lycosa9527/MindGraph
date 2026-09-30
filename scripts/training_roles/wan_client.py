"""DashScope Wan / HappyHorse video submit / poll / download, plus Qwen-Audio TTS."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests

from scripts.training_roles.catalog import NEGATIVE, SHELL, RoleAction
from scripts.training_roles.env import dashscope_workspace
from scripts.training_roles.role_voices import MAX_REFERENCE_AUDIO

MODEL = "wan2.7-i2v-2026-04-25"
WAN3_VIDEO_PRIME = "wan3.0-video-prime"
HAPPYHORSE_T2V = "happyhorse-1.1-t2v"
QWEN_AUDIO_TTS = "qwen-audio-3.1-tts-flash"
REFERENCE_AUDIO = "reference_audio"
FALLBACK = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_POLL_SECONDS = 600
LONG_POLL_SECONDS = 1800


def _bases() -> tuple[str, str]:
    workspace = dashscope_workspace()
    primary = f"https://{workspace}.cn-beijing.maas.aliyuncs.com/api/v1"
    return primary, FALLBACK


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
        "X-DashScope-WorkSpace": dashscope_workspace(),
    }


def _tts_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-WorkSpace": dashscope_workspace(),
    }


def build_video_body(
    model: str,
    prompt: str,
    *,
    negative: str = "",
    media: list[dict[str, str]] | None = None,
    resolution: str = "720P",
    duration: int = 5,
    ratio: str | None = None,
    audio: bool | None = None,
    prompt_extend: bool = False,
    watermark: bool = False,
) -> dict[str, Any]:
    """Build a video-synthesis request body for Wan I2V / Wan 3.0 / HappyHorse."""
    payload: dict[str, Any] = {"prompt": prompt}
    if negative and model != HAPPYHORSE_T2V:
        payload["negative_prompt"] = negative
    if media:
        payload["media"] = media
    parameters: dict[str, Any] = {
        "resolution": resolution,
        "duration": duration,
        "watermark": watermark,
    }
    if ratio:
        parameters["ratio"] = ratio
    if model != HAPPYHORSE_T2V:
        parameters["prompt_extend"] = prompt_extend
    if audio is not None and model != HAPPYHORSE_T2V:
        parameters["audio"] = audio
    return {"model": model, "input": payload, "parameters": parameters}


def _post_video(api_key: str, body: dict[str, Any], label: str) -> str:
    last_error: Exception | None = None
    for base in _bases():
        for attempt in range(1, 4):
            try:
                response = requests.post(
                    f"{base}/services/aigc/video-generation/video-synthesis",
                    headers=_headers(api_key),
                    json=body,
                    timeout=180,
                )
                data = response.json()
                task_id = (data.get("output") or {}).get("task_id")
                if isinstance(task_id, str) and task_id:
                    print(f"{label} submitted {task_id}", flush=True)
                    return task_id
                last_error = RuntimeError(str(data.get("message") or "submit failed"))
                print(f"{label} submit {data.get('code')} {data.get('message')}", flush=True)
            except requests.RequestException as exc:
                last_error = exc
                print(f"{label} transport {type(exc).__name__}", flush=True)
                time.sleep(2 * attempt)
    raise RuntimeError(f"{label} submit failed: {last_error}")


def submit_i2v(
    api_key: str,
    frame_url: str,
    prompt: str,
    negative: str,
    label: str,
    *,
    resolution: str = "720P",
    duration: int = 5,
) -> str:
    """Submit one I2V clip. Defaults stay 5s 720P for Course Builder roles."""
    body = build_video_body(
        MODEL,
        prompt,
        negative=negative,
        media=[{"type": "first_frame", "url": frame_url}],
        resolution=resolution,
        duration=duration,
    )
    return _post_video(api_key, body, label)


def submit_video(
    api_key: str,
    prompt: str,
    label: str,
    *,
    model: str,
    negative: str = "",
    media: list[dict[str, str]] | None = None,
    resolution: str = "1080P",
    duration: int = 15,
    ratio: str = "16:9",
    audio: bool | None = None,
    prompt_extend: bool = False,
    watermark: bool = False,
) -> str:
    """Submit T2V or reference-image video for Wan 3.0 / HappyHorse."""
    body = build_video_body(
        model,
        prompt,
        negative=negative,
        media=media,
        resolution=resolution,
        duration=duration,
        ratio=ratio,
        audio=audio,
        prompt_extend=prompt_extend,
        watermark=watermark,
    )
    return _post_video(api_key, body, label)


def post_i2v(api_key: str, frame_url: str, action: RoleAction) -> str:
    """Submit one Course Builder role clip. Returns task id."""
    return submit_i2v(
        api_key,
        frame_url,
        SHELL + action["prompt"],
        NEGATIVE,
        action["id"],
    )


def poll_video_url(
    api_key: str,
    task_id: str,
    label: str,
    *,
    timeout_seconds: int = DEFAULT_POLL_SECONDS,
) -> str:
    """Block until the Wan task succeeds and return the MP4 URL."""
    started = time.time()
    last = ""
    last_print = started
    workspace = dashscope_workspace()
    while time.time() - started < timeout_seconds:
        data: dict[str, Any] | None = None
        for base in _bases():
            try:
                response = requests.get(
                    f"{base}/tasks/{task_id}",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "X-DashScope-WorkSpace": workspace,
                    },
                    timeout=30,
                )
                payload = response.json()
                if isinstance(payload, dict):
                    data = payload
                    break
            except requests.RequestException:
                continue
        if data is None:
            time.sleep(8)
            continue
        raw_output = data.get("output")
        output = raw_output if isinstance(raw_output, dict) else {}
        status = str(output.get("task_status") or "")
        now = time.time()
        if status != last or now - last_print >= 24:
            print(f"{label} {status or 'WAIT'} {int(now - started)}s", flush=True)
            last = status
            last_print = now
        if status == "SUCCEEDED":
            video_url = output.get("video_url")
            if isinstance(video_url, str) and video_url:
                return video_url
            raise RuntimeError(f"{label} missing video_url")
        if status in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise RuntimeError(f"{label} {status}: {output.get('message') or data.get('message')}")
        time.sleep(8)
    raise TimeoutError(f"{label} timed out")


def download_mp4(url: str, dest: Path) -> None:
    """Write the Wan MP4 with a few retries."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            with requests.get(url, stream=True, timeout=180) as response:
                response.raise_for_status()
                dest.write_bytes(response.content)
            print(f"mp4 {dest.name} {dest.stat().st_size}", flush=True)
            return
        except requests.RequestException as exc:
            last_error = exc
            print(f"download retry {attempt} {type(exc).__name__}", flush=True)
            time.sleep(2 * attempt)
    raise RuntimeError(f"download failed: {last_error}")


def build_tts_body(
    text: str,
    voice: str,
    *,
    model: str = QWEN_AUDIO_TTS,
    audio_format: str = "wav",
    sample_rate: int = 24000,
) -> dict[str, Any]:
    """Body for non-streaming Qwen-Audio-TTS SpeechSynthesizer."""
    return {
        "model": model,
        "input": {
            "text": text,
            "voice": voice,
            "format": audio_format,
            "sample_rate": sample_rate,
            "language_hints": ["zh"],
        },
    }


def extract_tts_audio_url(payload: dict[str, Any]) -> str:
    """Public audio URL from a completed SpeechSynthesizer response."""
    output = payload.get("output")
    if not isinstance(output, dict):
        return ""
    audio = output.get("audio")
    if not isinstance(audio, dict):
        return ""
    url = audio.get("url")
    return url if isinstance(url, str) else ""


def reference_audio(url: str) -> dict[str, str]:
    """One Wan 3 timbre clip. 音频N follows the order these are appended."""
    return {"type": REFERENCE_AUDIO, "url": url}


def with_reference_audio(
    images: list[dict[str, str]],
    audio_urls: list[str],
) -> list[dict[str, str]]:
    """Append timbre clips after the reference images.

    Wan counts images and audio separately, so 图1 stays the first image
    and 音频1 stays the first audio URL. Set ``audio=True`` on the video
    job and put ``口型同步`` in the prompt.
    """
    if len(audio_urls) > MAX_REFERENCE_AUDIO:
        raise ValueError(f"Wan 3 accepts at most {MAX_REFERENCE_AUDIO} reference audio clips")
    return [*images, *[reference_audio(url) for url in audio_urls]]


def synthesize_tts(api_key: str, text: str, voice: str, *, model: str = QWEN_AUDIO_TTS) -> str:
    """Synthesize one line and return the 24-hour audio URL."""
    body = build_tts_body(text, voice, model=model)
    last_error: Exception | None = None
    for base in _bases():
        try:
            response = requests.post(
                f"{base}/services/audio/tts/SpeechSynthesizer",
                headers=_tts_headers(api_key),
                json=body,
                timeout=120,
            )
            data = response.json()
            if not isinstance(data, dict):
                last_error = RuntimeError("TTS returned a non-object payload")
                continue
            url = extract_tts_audio_url(data)
            if url:
                print(f"tts {voice} ready", flush=True)
                return url
            message = str(data.get("message") or "TTS missing audio url")
            last_error = RuntimeError(message)
            print(f"tts {data.get('code')} {message}", flush=True)
        except requests.RequestException as exc:
            last_error = exc
            print(f"tts transport {type(exc).__name__}", flush=True)
    raise RuntimeError(f"TTS submit failed: {last_error}")
