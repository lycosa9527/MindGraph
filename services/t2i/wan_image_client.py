"""DashScope Wan 2.7 image async client (组图 / sequential frames)."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from config.settings import config
from services.infrastructure.http.error_handler import LLMProviderError

logger = logging.getLogger(__name__)

DEFAULT_WAN_IMAGE_MODEL = "wan2.7-image"
WAN_MAX_N = 12
DEFAULT_WAN_SIZE = "1920*1080"
_POLL_INTERVAL_SECONDS = 2.0
# Keep under Celery soft limit when several batches run sequentially.
_POLL_TIMEOUT_SECONDS = 420.0
_POLL_HEARTBEAT_SECONDS = 30.0
_HTTP_ATTEMPTS = 8


def _format_log_context(log_context: Optional[str]) -> str:
    """Suffix for Wan log lines (e.g. conversation=… batch=1/3)."""
    cleaned = (log_context or "").strip()
    if not cleaned:
        return ""
    return f" {cleaned}"


_TRANSIENT_HTTP_ERRORS = (
    requests.RequestException,
    ConnectionError,
    TimeoutError,
    OSError,
)


@dataclass(frozen=True)
class WanImageBatchResult:
    """Result of one Wan async 组图 job."""

    image_urls: tuple[str, ...]
    task_id: str
    size: Optional[str]
    image_count: int
    usage: Optional[dict[str, Any]]


def _dashscope_api_key() -> str:
    """Prefer DASHSCOPE_API_KEY, fall back to QWEN_API_KEY."""
    explicit = (getattr(config, "DASHSCOPE_API_KEY", None) or "").strip()
    if explicit:
        return explicit
    qwen = (config.QWEN_API_KEY or "").strip()
    if qwen:
        return qwen
    raise RuntimeError("QWEN_API_KEY / DASHSCOPE_API_KEY is not configured")


def _api_v1_base() -> str:
    """DashScope ``/api/v1`` base without trailing slash issues."""
    return (config.DASHSCOPE_API_URL or "").rstrip("/")


def clamp_wan_n(n: int) -> int:
    """Clamp frame count to Wan 组图 range [1, 12]."""
    return max(1, min(int(n), WAN_MAX_N))


def extract_image_urls_from_task_output(output: Any) -> list[str]:
    """Collect ordered image URLs from a Wan task output payload."""
    if not isinstance(output, dict):
        return []
    urls: list[str] = []
    choices = output.get("choices")
    if not isinstance(choices, list):
        return urls
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type not in (None, "image"):
                continue
            image = part.get("image")
            if isinstance(image, str) and image.strip():
                urls.append(image.strip())
    return urls


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    json_body: Optional[dict[str, Any]] = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Sync HTTP JSON helper with retries for flaky TLS paths."""
    last_exc: Optional[BaseException] = None
    for attempt in range(_HTTP_ATTEMPTS):
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=timeout,
            )
            try:
                data = response.json()
            except ValueError as exc:
                raise LLMProviderError(f"Wan {method} non-JSON HTTP {response.status_code}") from exc
            if response.status_code >= 400:
                code = data.get("code") if isinstance(data, dict) else None
                message = data.get("message") if isinstance(data, dict) else str(data)
                raise LLMProviderError(f"Wan {method} failed HTTP {response.status_code}: {code or ''} {message}")
            if not isinstance(data, dict):
                raise LLMProviderError(f"Wan {method} returned non-object JSON")
            return data
        except _TRANSIENT_HTTP_ERRORS as exc:
            last_exc = exc
            logger.warning(
                "[WanImage] %s transient error attempt=%s: %s",
                method,
                attempt + 1,
                exc,
            )
            time.sleep(min(1.5 * (2**attempt), 15.0))
    raise LLMProviderError(f"Wan {method} transport failed: {last_exc}") from last_exc


async def submit_wan_image_task(
    *,
    prompt: str,
    model: str = DEFAULT_WAN_IMAGE_MODEL,
    n: int = 1,
    size: str = DEFAULT_WAN_SIZE,
    watermark: bool = False,
    enable_sequential: bool = True,
    api_key: Optional[str] = None,
    log_context: Optional[str] = None,
) -> str:
    """
    Create an async Wan image-generation task.

    Returns DashScope ``task_id``.
    """
    cleaned = (prompt or "").strip()
    if not cleaned:
        raise ValueError("Wan prompt is required")
    key = (api_key or _dashscope_api_key()).strip()
    base = _api_v1_base()
    url = f"{base}/services/aigc/image-generation/generation"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "X-DashScope-Async": "enable",
    }
    payload: dict[str, Any] = {
        "model": (model or DEFAULT_WAN_IMAGE_MODEL).strip(),
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": cleaned[:5000]}],
                }
            ]
        },
        "parameters": {
            "enable_sequential": bool(enable_sequential),
            "n": clamp_wan_n(n),
            "size": (size or DEFAULT_WAN_SIZE).strip(),
            "watermark": bool(watermark),
        },
    }
    ctx = _format_log_context(log_context)
    data = await asyncio.to_thread(
        _request_json,
        "POST",
        url,
        headers=headers,
        json_body=payload,
        timeout=60.0,
    )
    output = data.get("output") if isinstance(data.get("output"), dict) else {}
    task_id = output.get("task_id") if isinstance(output, dict) else None
    if not isinstance(task_id, str) or not task_id.strip():
        code = data.get("code")
        message = data.get("message")
        logger.error(
            "[WanImage] Submit missing task_id n=%s model=%s%s code=%s message=%s",
            clamp_wan_n(n),
            model,
            ctx,
            code,
            message,
        )
        raise LLMProviderError(f"Wan submit missing task_id: {code or ''} {message or data}")
    logger.info(
        "[WanImage] Submitted task_id=%s n=%s model=%s%s",
        task_id,
        clamp_wan_n(n),
        model,
        ctx,
    )
    return task_id.strip()


async def poll_wan_image_task(
    task_id: str,
    *,
    api_key: Optional[str] = None,
    poll_interval: float = _POLL_INTERVAL_SECONDS,
    timeout_seconds: float = _POLL_TIMEOUT_SECONDS,
    log_context: Optional[str] = None,
) -> WanImageBatchResult:
    """Poll Wan task until SUCCEEDED / FAILED / timeout."""
    key = (api_key or _dashscope_api_key()).strip()
    base = _api_v1_base()
    url = f"{base}/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {key}"}
    loop = asyncio.get_running_loop()
    started = loop.time()
    deadline = started + max(30.0, float(timeout_seconds))
    ctx = _format_log_context(log_context)
    last_heartbeat = started - _POLL_HEARTBEAT_SECONDS
    last_logged_status = ""

    while True:
        now = loop.time()
        if now > deadline:
            logger.error(
                "[WanImage] Timed out task_id=%s elapsed=%.1fs timeout=%.0fs%s",
                task_id,
                now - started,
                timeout_seconds,
                ctx,
            )
            raise LLMProviderError(f"Wan task timed out: {task_id}")
        try:
            data = await asyncio.to_thread(
                _request_json,
                "GET",
                url,
                headers=headers,
                timeout=60.0,
            )
        except LLMProviderError as exc:
            # Keep polling through flaky TLS; only abort on hard timeout above.
            logger.warning(
                "[WanImage] poll transport hiccup task_id=%s elapsed=%.1fs%s: %s",
                task_id,
                loop.time() - started,
                ctx,
                exc,
            )
            await asyncio.sleep(max(1.0, float(poll_interval)))
            continue
        output = data.get("output") if isinstance(data.get("output"), dict) else {}
        task_status = ""
        if isinstance(output, dict):
            raw_status = output.get("task_status")
            if isinstance(raw_status, str):
                task_status = raw_status.upper()
        if task_status in {"PENDING", "RUNNING", ""}:
            now = loop.time()
            status_label = task_status or "UNKNOWN"
            status_changed = status_label != last_logged_status
            due_heartbeat = (now - last_heartbeat) >= _POLL_HEARTBEAT_SECONDS
            if status_changed or due_heartbeat:
                logger.info(
                    "[WanImage] Waiting task_id=%s status=%s elapsed=%.1fs timeout=%.0fs%s",
                    task_id,
                    status_label,
                    now - started,
                    timeout_seconds,
                    ctx,
                )
                last_heartbeat = now
                last_logged_status = status_label
            await asyncio.sleep(max(0.5, float(poll_interval)))
            continue
        if task_status == "SUCCEEDED":
            urls = extract_image_urls_from_task_output(output)
            if not urls:
                logger.error(
                    "[WanImage] Succeeded without images task_id=%s elapsed=%.1fs%s",
                    task_id,
                    loop.time() - started,
                    ctx,
                )
                raise LLMProviderError(f"Wan task succeeded without images: {task_id}")
            usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
            size_val = None
            if isinstance(usage, dict) and isinstance(usage.get("size"), str):
                size_val = usage.get("size")
            image_count = len(urls)
            if isinstance(usage, dict) and usage.get("image_count") is not None:
                try:
                    image_count = int(usage["image_count"])
                except (TypeError, ValueError):
                    image_count = len(urls)
            logger.info(
                "[WanImage] Succeeded task_id=%s urls=%s elapsed=%.1fs size=%s%s",
                task_id,
                len(urls),
                loop.time() - started,
                size_val or "-",
                ctx,
            )
            return WanImageBatchResult(
                image_urls=tuple(urls),
                task_id=task_id,
                size=size_val,
                image_count=image_count,
                usage=usage,
            )
        code = data.get("code")
        message = data.get("message") or task_status
        logger.error(
            "[WanImage] Failed task_id=%s status=%s elapsed=%.1fs code=%s message=%s%s",
            task_id,
            task_status,
            loop.time() - started,
            code,
            message,
            ctx,
        )
        raise LLMProviderError(f"Wan task failed status={task_status}: {code or ''} {message}")


async def generate_wan_image_batch(
    *,
    prompt: str,
    model: str = DEFAULT_WAN_IMAGE_MODEL,
    n: int = 1,
    size: str = DEFAULT_WAN_SIZE,
    watermark: bool = False,
    enable_sequential: bool = True,
    log_context: Optional[str] = None,
) -> WanImageBatchResult:
    """Submit Wan async 组图 and wait for image URLs."""
    task_id = await submit_wan_image_task(
        prompt=prompt,
        model=model,
        n=n,
        size=size,
        watermark=watermark,
        enable_sequential=enable_sequential,
        log_context=log_context,
    )
    return await poll_wan_image_task(task_id, log_context=log_context)


def _download_bytes_sync(image_url: str, timeout: float) -> bytes:
    last_exc: Optional[BaseException] = None
    download_errors = _TRANSIENT_HTTP_ERRORS + (RuntimeError,)
    for attempt in range(_HTTP_ATTEMPTS):
        try:
            response = requests.get(image_url, timeout=timeout)
            if response.status_code != 200:
                raise RuntimeError(f"Failed to download image: HTTP {response.status_code}")
            data = response.content
            if not data:
                raise RuntimeError("Failed to download image: empty body")
            return data
        except download_errors as exc:
            last_exc = exc
            logger.warning(
                "[WanImage] download transient error attempt=%s: %s",
                attempt + 1,
                exc,
            )
            time.sleep(min(1.5 * (2**attempt), 12.0))
    raise RuntimeError(f"Failed to download image: {last_exc}") from last_exc


async def download_image_bytes(image_url: str) -> bytes:
    """Download generated image bytes from a temporary DashScope URL."""
    timeout = float(config.T2I_IMAGE_DOWNLOAD_TIMEOUT)
    return await asyncio.to_thread(_download_bytes_sync, image_url, timeout)
