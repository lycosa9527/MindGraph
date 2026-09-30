"""One instrumental bed for the October promo. Foley stays on the Wan clips."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests

from scripts.october_update_promo.catalog import BGM_PROMPT, FUN_MUSIC
from scripts.training_roles.env import dashscope_workspace
from scripts.training_roles.wan_client import FALLBACK

_MUSIC_PATH = "services/audio/music/generation"


def _bases() -> tuple[str, str]:
    workspace = dashscope_workspace()
    primary = f"https://{workspace}.cn-beijing.maas.aliyuncs.com/api/v1"
    return primary, FALLBACK


def build_music_body(prompt: str = BGM_PROMPT) -> dict[str, Any]:
    """Instrumental Fun-Music request. Lyrics and singer gender stay off."""
    return {
        "model": FUN_MUSIC,
        "input": {
            "prompt": prompt,
            "is_instrumental": True,
            "format": "mp3",
        },
    }


def _audio_url(payload: dict[str, Any]) -> str:
    output = payload.get("output")
    if not isinstance(output, dict):
        return ""
    audio = output.get("audio")
    if not isinstance(audio, dict):
        return ""
    url = audio.get("url")
    return url if isinstance(url, str) else ""


def synthesize_bgm(api_key: str, prompt: str = BGM_PROMPT) -> str:
    """Return the 24-hour URL of the instrumental bed."""
    body = build_music_body(prompt)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-WorkSpace": dashscope_workspace(),
    }
    last_error: Exception | None = None
    for base in _bases():
        try:
            response = requests.post(
                f"{base}/{_MUSIC_PATH}",
                headers=headers,
                json=body,
                timeout=300,
            )
            data = response.json()
            if not isinstance(data, dict):
                last_error = RuntimeError("music returned a non-object payload")
                continue
            url = _audio_url(data)
            if url:
                print("bgm ready", flush=True)
                return url
            message = str(data.get("message") or "music missing audio url")
            last_error = RuntimeError(message)
            print(f"bgm {data.get('code')} {message}", flush=True)
        except requests.RequestException as exc:
            last_error = exc
            print(f"bgm transport {type(exc).__name__}", flush=True)
            time.sleep(2)
    raise RuntimeError(f"BGM submit failed: {last_error}")


def download_audio(url: str, dest: Path) -> None:
    """Write the bed with a few retries."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with requests.get(url, stream=True, timeout=180) as response:
                response.raise_for_status()
                dest.write_bytes(response.content)
            print(f"bgm {dest.name} {dest.stat().st_size}", flush=True)
            return
        except requests.RequestException as exc:
            last_error = exc
            print(f"bgm download retry {attempt} {type(exc).__name__}", flush=True)
            time.sleep(2 * attempt)
    raise RuntimeError(f"BGM download failed: {last_error}")
