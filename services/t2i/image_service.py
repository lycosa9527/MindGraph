"""Orchestrate ZhiHui text-to-image generation and COS persistence."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

from config.settings import config
from services.t2i.image_client import image_client, resolve_image_model
from services.t2i.prompt_enhance import enhance_prompt_for_k12
from services.zhihui.storage import build_generation_key, put_bytes

logger = logging.getLogger(__name__)

MIN_PROMPT_LENGTH = 1
MAX_PROMPT_LENGTH = 1000


@dataclass(frozen=True)
class T2IGenerationResult:
    """Result of a successful image generation + COS upload."""

    generation_id: str
    logical_key: str
    content_type: str
    original_prompt: str
    enhanced_prompt: Optional[str]
    size: str
    usage_data: Optional[dict[str, Any]]
    image_bytes_len: int


def validate_prompt(prompt: str) -> str:
    """Validate and normalize the user prompt."""
    cleaned = (prompt or "").strip()
    if len(cleaned) < MIN_PROMPT_LENGTH:
        raise ValueError("Prompt is required")
    if len(cleaned) > MAX_PROMPT_LENGTH:
        raise ValueError(f"Prompt is too long (max {MAX_PROMPT_LENGTH} characters)")
    return cleaned


async def _download_image_bytes(image_url: str) -> bytes:
    """Download generated image bytes from DashScope temporary URL."""
    timeout = aiohttp.ClientTimeout(total=config.T2I_IMAGE_DOWNLOAD_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(image_url) as response:
            if response.status != 200:
                logger.error(
                    "[T2I] Download failed status=%s url_len=%s",
                    response.status,
                    len(image_url),
                )
                raise RuntimeError(f"Failed to download image: HTTP {response.status}")
            data = await response.read()
            if not data:
                logger.error("[T2I] Download returned empty body url_len=%s", len(image_url))
                raise RuntimeError("Failed to download image: empty body")
            return data


async def generate_and_store_image(
    prompt: str,
    *,
    model: Optional[str] = None,
    size: Optional[str] = None,
    watermark: bool = False,
    negative_prompt: str = "",
    prompt_extend: bool = True,
    reference_images: Optional[list[str]] = None,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    api_key_id: Optional[int] = None,
    enhance: Optional[bool] = None,
) -> T2IGenerationResult:
    """
    Enhance (optional), generate via DashScope, upload to COS/local storage.

    Does not write Postgres history — caller persists the row.
    """
    original = validate_prompt(prompt)
    usage_data: Optional[dict[str, Any]] = None
    final_prompt = original
    enhanced: Optional[str] = None
    resolved_model = resolve_image_model(model)
    refs = [item.strip() for item in (reference_images or []) if item and item.strip()]

    do_enhance = config.T2I_ENABLE_PROMPT_ENHANCEMENT if enhance is None else enhance
    # Skip K12 text rewrite when the user supplies reference images (I2I).
    if do_enhance and not refs:
        final_prompt, usage_data = await enhance_prompt_for_k12(
            original,
            user_id=user_id,
            organization_id=organization_id,
            api_key_id=api_key_id,
        )
        if final_prompt != original:
            enhanced = final_prompt

    # Empty / omitted size → env default, else API auto resolution.
    resolved_size = (size or config.IMAGE_DEFAULT_SIZE or "").strip() or None
    logger.info(
        "[T2I] Generate start model=%s size=%s prompt_len=%s refs=%s enhance=%s",
        resolved_model,
        resolved_size or "auto",
        len(final_prompt),
        len(refs),
        bool(enhanced),
    )
    remote_url = await image_client.generate_image(
        prompt=final_prompt,
        model=resolved_model,
        size=resolved_size,
        prompt_extend=False if enhanced else prompt_extend,
        watermark=watermark,
        negative_prompt=negative_prompt or "",
        reference_images=refs or None,
    )
    image_bytes = await _download_image_bytes(remote_url)
    generation_id = str(uuid.uuid4())
    logical_key = build_generation_key(generation_id=generation_id, suffix=".png")
    await put_bytes(logical_key, image_bytes, content_type="image/png")

    logger.info(
        "[T2I] Stored generation id=%s model=%s bytes=%s key=%s refs=%s",
        generation_id,
        resolved_model,
        len(image_bytes),
        logical_key,
        len(refs),
    )
    return T2IGenerationResult(
        generation_id=generation_id,
        logical_key=logical_key,
        content_type="image/png",
        original_prompt=original,
        enhanced_prompt=enhanced,
        size=resolved_size or "auto",
        usage_data=usage_data,
        image_bytes_len=len(image_bytes),
    )
