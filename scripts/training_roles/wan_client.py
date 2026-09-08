"""DashScope Wan I2V submit / poll / download."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests

from scripts.training_roles.catalog import NEGATIVE, SHELL, RoleAction
from scripts.training_roles.env import dashscope_workspace

MODEL = "wan2.7-i2v-2026-04-25"
FALLBACK = "https://dashscope.aliyuncs.com/api/v1"


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
    body: dict[str, Any] = {
        "model": MODEL,
        "input": {
            "prompt": prompt,
            "negative_prompt": negative,
            "media": [{"type": "first_frame", "url": frame_url}],
        },
        "parameters": {
            "resolution": resolution,
            "duration": duration,
            "prompt_extend": False,
            "watermark": False,
        },
    }
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


def post_i2v(api_key: str, frame_url: str, action: RoleAction) -> str:
    """Submit one Course Builder role clip. Returns task id."""
    return submit_i2v(
        api_key,
        frame_url,
        SHELL + action["prompt"],
        NEGATIVE,
        action["id"],
    )


def poll_video_url(api_key: str, task_id: str, label: str) -> str:
    """Block until the Wan task succeeds and return the MP4 URL."""
    started = time.time()
    last = ""
    workspace = dashscope_workspace()
    while time.time() - started < 600:
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
        if status != last:
            print(f"{label} {status} {int(time.time() - started)}s", flush=True)
            last = status
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
