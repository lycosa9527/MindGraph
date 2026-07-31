"""Live smoke: Maite OCR upload path + qwen3.7-flash extraction.

Usage (WSL, repo root, conda python313):
  PYTHONPATH=. python scripts/smoke_maite_ocr.py
  PYTHONPATH=. python scripts/smoke_maite_ocr.py --image /path/to.png
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

from dotenv import load_dotenv

from services.llm import llm_service
from services.maite.domain.problem_service import ProblemService
from services.maite.llm.router import route
from services.redis.redis_client import init_redis_sync

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = Path("/mnt/c/Users/roywa/Downloads/ScreenShot_2026-07-31_172931_887.png")


async def run_ocr(image_path: Path) -> dict:
    """Exercise ProblemService.ocr_extract against a real image."""
    if not image_path.is_file():
        raise FileNotFoundError(image_path)

    route_ctx = route("ocr_extract", has_image=True)
    print("=" * 72)
    print(f"IMAGE: {image_path}")
    print(f"SIZE: {image_path.stat().st_size} bytes")
    print(f"ROUTE_MODEL: {route_ctx.model}")
    print(f"REQUIRES_VISION: {route_ctx.requires_vision}")

    image_bytes = image_path.read_bytes()
    service = ProblemService(MagicMock())
    started = time.perf_counter()
    result = await service.ocr_extract(
        user_id=999002,
        organization_id=None,
        image_bytes=image_bytes,
        mime_type="image/png",
        endpoint_path="/smoke/maite/problems/ocr",
    )
    elapsed = time.perf_counter() - started

    payload = {
        "stored_path": result.stored_path,
        "confidence": result.confidence,
        "raw_text": result.raw_text,
        "clean_text": result.clean_text,
        "extra": result.extra,
        "elapsed_seconds": round(elapsed, 3),
        "model": route_ctx.model,
    }
    print("-" * 72)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"ELAPSED: {elapsed:.3f}s")
    return payload


async def main() -> None:
    """Run Maite OCR smoke against one screenshot."""
    parser = argparse.ArgumentParser(description="Maite OCR live smoke")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument(
        "--keep-rate-limit",
        action="store_true",
        help="Keep DashScope rate limiting (default: disable for smoke reliability)",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    if not args.keep_rate_limit:
        # WSL/localhost Redis acquire can hang; smoke only needs the model path.
        os.environ["DASHSCOPE_RATE_LIMITING_ENABLED"] = "false"
    if not os.getenv("QWEN_API_KEY"):
        raise SystemExit("QWEN_API_KEY missing")
    if not init_redis_sync():
        raise SystemExit("Redis unavailable — start Redis or check REDIS_URL")
    llm_service.initialize()
    if "qwen3.7-flash" not in llm_service.client_manager.get_available_models():
        raise SystemExit("qwen3.7-flash not registered in ClientManager")
    if llm_service.rate_limiter is not None and not args.keep_rate_limit:
        llm_service.rate_limiter.enabled = False

    payload = await run_ocr(args.image.resolve())
    out = ROOT / "tmp" / "maite_ocr_smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE: {out}")

    if not (payload.get("clean_text") or "").strip():
        raise SystemExit("OCR returned empty clean_text")


if __name__ == "__main__":
    asyncio.run(main())
