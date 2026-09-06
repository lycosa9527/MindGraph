"""DashScope Wan 2.7 image submit / poll / download with reference stills."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from scripts.cat_office_battles.paths import WORK_DIR
from scripts.training_roles.env import dashscope_api_key, dashscope_workspace
from services.t2i.wan_image_client import extract_image_urls_from_task_output

FALLBACK = "https://dashscope.aliyuncs.com/api/v1"
MODEL = "wan2.7-image"


def _bases() -> tuple[str, str]:
    workspace = dashscope_workspace()
    primary = f"https://{workspace}.cn-beijing.maas.aliyuncs.com/api/v1"
    return primary, FALLBACK


def _headers(async_enable: bool = True) -> dict[str, str]:
    out = {
        "Authorization": f"Bearer {dashscope_api_key()}",
        "Content-Type": "application/json",
        "X-DashScope-WorkSpace": dashscope_workspace(),
    }
    if async_enable:
        out["X-DashScope-Async"] = "enable"
    return out


def jpeg_data_url(src: Path, max_w: int = 1024) -> str:
    """Shrink a still and return a JPEG data URL."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(src).convert("RGB")
    width, height = image.size
    if width > max_w:
        height = int(height * (max_w / width))
        image = image.resize((max_w, height), Image.Resampling.LANCZOS)
    dest = WORK_DIR / f"ref-{src.stem}.jpg"
    image.save(dest, format="JPEG", quality=86, optimize=True)
    payload = base64.b64encode(dest.read_bytes()).decode("ascii")
    print(f"ref={dest.name} size={image.size} bytes={dest.stat().st_size}", flush=True)
    return f"data:image/jpeg;base64,{payload}"


def _post_json(path: str, body: dict[str, Any]) -> dict[str, Any]:
    last_error: Exception | None = None
    for base in _bases():
        url = f"{base}{path}"
        for attempt in range(1, 4):
            try:
                print(f"POST {base} attempt={attempt}", flush=True)
                response = requests.post(url, headers=_headers(), json=body, timeout=180)
                data = response.json()
                if response.status_code >= 400 or data.get("code"):
                    print(
                        json.dumps(
                            {k: data.get(k) for k in ("code", "message", "request_id")},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    last_error = RuntimeError(data.get("message") or f"http={response.status_code}")
                    continue
                if not isinstance(data, dict):
                    last_error = RuntimeError("non-object JSON")
                    continue
                return data
            except requests.RequestException as exc:
                last_error = exc
                print(f"transport {type(exc).__name__}", flush=True)
                time.sleep(2 * attempt)
    raise RuntimeError(f"submit failed: {last_error}")


def submit_storyboard(prompt: str, refs: list[Path], n: int) -> str:
    """Submit one sequential Wan 组图 job. Returns task id."""
    content: list[dict[str, str]] = [{"image": jpeg_data_url(path)} for path in refs]
    content.append({"text": prompt[:5000]})
    body: dict[str, Any] = {
        "model": MODEL,
        "input": {"messages": [{"role": "user", "content": content}]},
        "parameters": {
            "n": max(1, min(int(n), 12)),
            "size": "1920*1080",
            "watermark": False,
            "enable_sequential": True,
        },
    }
    submitted = _post_json("/services/aigc/image-generation/generation", body)
    output = submitted.get("output") if isinstance(submitted.get("output"), dict) else {}
    task_id = output.get("task_id") if isinstance(output, dict) else None
    if not isinstance(task_id, str) or not task_id:
        print(json.dumps(submitted, ensure_ascii=False)[:1000], flush=True)
        raise RuntimeError("missing task_id")
    print(f"task_id={task_id}", flush=True)
    return task_id


def poll_storyboard(task_id: str) -> list[str]:
    """Poll until SUCCEEDED and return image URLs."""
    started = time.time()
    last = ""
    workspace = dashscope_workspace()
    while time.time() - started < 420:
        data: dict[str, Any] | None = None
        last_error: Exception | None = None
        for base in _bases():
            try:
                response = requests.get(
                    f"{base}/tasks/{task_id}",
                    headers={
                        "Authorization": f"Bearer {dashscope_api_key()}",
                        "X-DashScope-WorkSpace": workspace,
                    },
                    timeout=30,
                )
                payload = response.json()
                if isinstance(payload, dict):
                    data = payload
                    break
            except requests.RequestException as exc:
                last_error = exc
        if data is None:
            print(f"poll transport {type(last_error).__name__}", flush=True)
            time.sleep(8)
            continue
        raw_output = data.get("output")
        output: dict[str, Any] = raw_output if isinstance(raw_output, dict) else {}
        status = str(output.get("task_status") or "")
        if status != last:
            print(f"poll status={status} elapsed={int(time.time() - started)}s", flush=True)
            last = status
        if status == "SUCCEEDED":
            urls = extract_image_urls_from_task_output(output)
            if not urls and isinstance(output.get("image_url"), str):
                urls = [output["image_url"]]
            if not urls:
                print(json.dumps(output, ensure_ascii=False)[:1500], flush=True)
                raise RuntimeError(f"no image urls: {task_id}")
            return urls
        if status in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise RuntimeError(f"task {status}: {output.get('message') or data.get('message')}")
        time.sleep(5)
    raise TimeoutError(f"poll timed out: {task_id}")


def download_image(url: str, dest: Path) -> None:
    """Write one generated still."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        dest.write_bytes(response.content)
    print(f"saved {dest} bytes={dest.stat().st_size}", flush=True)
