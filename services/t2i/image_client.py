"""DashScope MultiModalConversation client for ZhiHui Qwen Image 3.0 T2I."""

from __future__ import annotations

import asyncio
import logging
from http import HTTPStatus
from typing import Any, NoReturn, Optional

import dashscope
from dashscope import MultiModalConversation

from config.settings import config
from models.requests.requests_t2i import ALLOWED_IMAGE_MODELS, DEFAULT_IMAGE_MODEL
from services.infrastructure.http.error_handler import LLMProviderError
from services.llm.error_parsers.dashscope_error_parser import parse_dashscope_error

logger = logging.getLogger(__name__)

# Qwen Image 3.0 docs: seed ∈ [0, 2147483647], n ∈ [1, 6].
_SEED_MIN = 0
_SEED_MAX = 2147483647
_N_MIN = 1
_N_MAX = 6

# Common UX sizes → API ``宽*高`` (pixel area within 512²–2048²).
SIZE_MAPPING = {
    "1024*1024": "1024*1024",
    "1328*1328": "1328*1328",
    "1536*1536": "1536*1536",
    "2048*2048": "2048*2048",
    "1280*1280": "1280*1280",
    "1280*720": "1280*720",
    "1664*928": "1664*928",
    "1920*1080": "1920*1080",
    "1280*960": "1280*960",
    "1600*1200": "1600*1200",
    "1200*800": "1200*800",
    "1536*1024": "1536*1024",
    "720*1280": "720*1280",
    "928*1664": "928*1664",
    "1080*1920": "1080*1920",
    "960*1280": "960*1280",
    "1200*1600": "1200*1600",
    "800*1200": "800*1200",
    "1024*1536": "1024*1536",
    "1792*768": "1792*768",
    "1344*576": "1344*576",
    "768*1792": "768*1792",
    "576*1344": "576*1344",
}


def _dashscope_api_key() -> str:
    """Prefer DASHSCOPE_API_KEY, fall back to QWEN_API_KEY (same CAM key)."""
    explicit = (getattr(config, "DASHSCOPE_API_KEY", None) or "").strip()
    if explicit:
        return explicit
    qwen = (config.QWEN_API_KEY or "").strip()
    if qwen:
        return qwen
    raise RuntimeError("QWEN_API_KEY / DASHSCOPE_API_KEY is not configured")


def resolve_image_model(model: Optional[str]) -> str:
    """Return an allowed Qwen Image 3.0 model id (default: qwen-image-3.0)."""
    candidate = (model or config.IMAGE_MODEL or "").strip()
    if candidate in ALLOWED_IMAGE_MODELS:
        return candidate
    default = (config.IMAGE_MODEL or DEFAULT_IMAGE_MODEL).strip()
    if default in ALLOWED_IMAGE_MODELS:
        return default
    return DEFAULT_IMAGE_MODEL


def normalize_size(size: Optional[str]) -> Optional[str]:
    """
    Map UX sizes to DashScope ``宽*高``.

    Returns ``None`` when unset so the model auto-picks resolution.
    Raises ``ValueError`` when a non-empty size is outside Qwen Image 3.0 limits.
    """
    if size is None:
        return None
    cleaned = size.strip()
    if not cleaned:
        return None
    if cleaned in SIZE_MAPPING:
        return SIZE_MAPPING[cleaned]
    try:
        width_s, height_s = cleaned.split("*")
        width, height = int(width_s), int(height_s)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Invalid size; use width*height (e.g. 1024*1024), area 512*512–2048*2048, aspect 1:8–8:1"
        ) from exc
    area = width * height
    if width < 1 or height < 1 or area < 512 * 512 or area > 2048 * 2048:
        raise ValueError("Invalid size; pixel area must be between 512*512 and 2048*2048")
    ratio = width / height
    if ratio < 1 / 8 or ratio > 8:
        raise ValueError("Invalid size; aspect ratio must be between 1:8 and 8:1")
    return f"{width}*{height}"


def _clamp_n(n: int) -> int:
    """Clamp output count to Qwen Image 3.0 range [1, 6]."""
    return max(_N_MIN, min(int(n), _N_MAX))


def _normalize_seed(seed: Optional[int]) -> Optional[int]:
    """Validate seed against DashScope image range, or return None."""
    if seed is None:
        return None
    value = int(seed)
    if value < _SEED_MIN or value > _SEED_MAX:
        raise ValueError(f"seed must be in [{_SEED_MIN}, {_SEED_MAX}]")
    return value


def _extract_image_url(content: Any) -> Optional[str]:
    """Pull the first image URL from a multimodal message content list."""
    if not isinstance(content, list):
        return None
    for item in content:
        if isinstance(item, dict):
            url = item.get("image")
            if isinstance(url, str) and url.strip():
                return url.strip()
            continue
        url = getattr(item, "image", None)
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def _response_request_id(response: Any) -> str:
    """DashScope request id for support / model-monitor lookup."""
    raw = getattr(response, "request_id", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return ""


def _raise_dashscope_image_error(response: Any) -> NoReturn:
    """Map DashScope failure to LLM* errors (content filter, billing, params)."""
    status_raw = getattr(response, "status_code", None)
    try:
        status = int(status_raw) if status_raw is not None else HTTPStatus.INTERNAL_SERVER_ERROR
    except (TypeError, ValueError):
        status = int(HTTPStatus.INTERNAL_SERVER_ERROR)
    code = getattr(response, "code", None) or ""
    message = getattr(response, "message", None) or "Unknown DashScope image error"
    request_id = _response_request_id(response)
    error_data = {
        "code": str(code),
        "message": str(message),
        "request_id": request_id,
    }
    logger.error(
        "[T2I] DashScope failed status=%s code=%s request_id=%s message=%s",
        status,
        code,
        request_id or "-",
        message,
    )
    exception, user_message = parse_dashscope_error(status, str(message), error_data)
    if isinstance(exception, LLMProviderError):
        exception.user_message = user_message
        raise exception
    setattr(exception, "user_message", user_message)
    raise exception


class ImageClient:
    """Client for DashScope Qwen Image 3.0 multimodal generation (T2I)."""

    def __init__(self) -> None:
        dashscope.base_http_api_url = config.DASHSCOPE_API_URL.rstrip("/")
        logger.info(
            "[T2I] ImageClient ready default_model=%s base=%s",
            resolve_image_model(None),
            config.DASHSCOPE_API_URL,
        )

    async def generate_image(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        size: Optional[str] = None,
        n: int = 1,
        prompt_extend: Optional[bool] = None,
        watermark: Optional[bool] = None,
        negative_prompt: str = "",
        seed: Optional[int] = None,
        reference_images: Optional[list[str]] = None,
    ) -> str:
        """
        Generate one image URL via MultiModalConversation (sync call in thread).

        Request shape matches Qwen Image 3.0: single user message. T2I uses one
        ``{"text": "..."}`` part; I2I prepends 1–3 ``{"image": "..."}`` parts.

        Returns a temporary DashScope result URL (download promptly; ~24h TTL).
        """
        cleaned_prompt = (prompt or "").strip()
        if not cleaned_prompt:
            raise ValueError("Prompt is required")

        api_key = _dashscope_api_key()
        resolved_model = resolve_image_model(model)
        resolved_size = normalize_size(size)
        resolved_seed = _normalize_seed(seed)
        if prompt_extend is None:
            prompt_extend = config.IMAGE_PROMPT_EXTEND
        if watermark is None:
            watermark = config.IMAGE_WATERMARK

        content: list[dict[str, str]] = []
        refs = [item.strip() for item in (reference_images or []) if item and item.strip()]
        if len(refs) > 3:
            raise ValueError("at most 3 reference images allowed")
        for image_ref in refs:
            content.append({"image": image_ref})
        content.append({"text": cleaned_prompt})

        messages = [
            {
                "role": "user",
                "content": content,
            }
        ]
        params: dict[str, Any] = {
            "api_key": api_key,
            "model": resolved_model,
            "messages": messages,
            "result_format": "message",
            "stream": False,
            "n": _clamp_n(n),
            "prompt_extend": bool(prompt_extend),
            "watermark": bool(watermark),
        }
        if resolved_size:
            params["size"] = resolved_size
        if negative_prompt:
            params["negative_prompt"] = negative_prompt.strip()
        if resolved_seed is not None:
            params["seed"] = resolved_seed

        logger.info(
            "[T2I] MultiModalConversation start model=%s size=%s prompt_len=%s refs=%s extend=%s",
            resolved_model,
            resolved_size or "auto",
            len(cleaned_prompt),
            len(refs),
            prompt_extend,
        )

        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: MultiModalConversation.call(**params),
            )
        except (OSError, TimeoutError, ConnectionError, RuntimeError, ValueError, TypeError) as exc:
            logger.error("[T2I] MultiModalConversation call failed: %s", exc, exc_info=True)
            raise RuntimeError(f"Image generation call failed: {exc}") from exc

        request_id = _response_request_id(response)
        status = getattr(response, "status_code", None)
        if status != HTTPStatus.OK:
            _raise_dashscope_image_error(response)

        output = getattr(response, "output", None)
        choices = getattr(output, "choices", None) if output is not None else None
        if not choices:
            logger.error("[T2I] Empty choices request_id=%s", request_id or "-")
            raise RuntimeError("No images generated")
        message = getattr(choices[0], "message", None)
        response_content = getattr(message, "content", None) if message is not None else None
        image_url = _extract_image_url(response_content)
        if not image_url:
            logger.error("[T2I] Empty image URL request_id=%s", request_id or "-")
            raise RuntimeError("Empty image URL from DashScope")
        logger.info(
            "[T2I] MultiModalConversation done request_id=%s url_len=%s",
            request_id or "-",
            len(image_url),
        )
        return image_url


image_client = ImageClient()
