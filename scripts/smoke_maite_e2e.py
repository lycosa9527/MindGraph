"""Live end-to-end Maite smoke: OCR → mentor decompose (complete + stream).

Usage (WSL, repo root, conda python313):
  PYTHONPATH=. python scripts/smoke_maite_e2e.py
  PYTHONPATH=. python scripts/smoke_maite_e2e.py --image /path/to.png
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from dotenv import load_dotenv

from services.llm import llm_service
from services.llm.llm_utils import stream_enable_thinking
from services.maite.domain.mentor_service import MentorService
from services.maite.domain.problem_service import ProblemService
from services.maite.llm.router import route
from services.maite.schemas.mentor import MentorDecomposeInput
from services.redis.redis_client import init_redis_sync

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = Path("/mnt/c/Users/roywa/Downloads/ScreenShot_2026-07-31_172931_887.png")

# Markers expected from this exam screenshot (functions / set D(x0)).
OCR_MARKERS = (
    "函数",
    "D(",
    "定义域",
    "奇函数",
    "单调",
)


def _audit_ocr(text: str) -> dict[str, Any]:
    hits = {marker: marker in text for marker in OCR_MARKERS}
    return {
        "chars": len(text),
        "marker_hits": hits,
        "markers_matched": sum(1 for ok in hits.values() if ok),
        "markers_total": len(OCR_MARKERS),
        "pass": sum(1 for ok in hits.values() if ok) >= 3 and len(text.strip()) > 80,
    }


def _audit_decompose(payload: dict[str, Any]) -> dict[str, Any]:
    condition = payload.get("condition_table") or []
    step = payload.get("step_table") or []
    model = payload.get("model_table") or []
    next_q = str(payload.get("next_question") or "").strip()
    opening = str(payload.get("opening_guidance") or "").strip()
    return {
        "condition_rows": len(condition) if isinstance(condition, list) else 0,
        "step_rows": len(step) if isinstance(step, list) else 0,
        "model_rows": len(model) if isinstance(model, list) else 0,
        "has_next_question": bool(next_q),
        "has_opening_guidance": bool(opening),
        "next_question_preview": next_q[:120],
        "pass": (
            isinstance(condition, list)
            and isinstance(step, list)
            and isinstance(model, list)
            and len(condition) > 0
            and len(step) > 0
            and len(model) > 0
            and bool(next_q)
        ),
    }


async def run_ocr(image_path: Path) -> dict[str, Any]:
    """Run OCR extraction and return audit payload."""
    route_ctx = route("ocr_extract", has_image=True)
    image_bytes = image_path.read_bytes()
    service = ProblemService(MagicMock())
    started = time.perf_counter()
    result = await service.ocr_extract(
        user_id=0,
        organization_id=None,
        image_bytes=image_bytes,
        mime_type="image/png",
        endpoint_path="/smoke/maite/e2e/ocr",
    )
    elapsed = time.perf_counter() - started
    text = (result.clean_text or result.raw_text or "").strip()
    audit = _audit_ocr(text)
    return {
        "stored_path": result.stored_path,
        "confidence": result.confidence,
        "raw_text": result.raw_text,
        "clean_text": result.clean_text,
        "elapsed_seconds": round(elapsed, 3),
        "model": route_ctx.model,
        "requires_vision": route_ctx.requires_vision,
        "thinking_helper_off": stream_enable_thinking(route_ctx.model) is False,
        "audit": audit,
    }


async def run_decompose_complete(question: str) -> dict[str, Any]:
    """Non-streaming mentor decompose."""
    route_ctx = route("mentor_decompose", has_image=False)
    service = MentorService()
    started = time.perf_counter()
    result = await service.decompose(
        MentorDecomposeInput(question=question),
        user_id=None,
        organization_id=None,
        endpoint_path="/smoke/maite/e2e/decompose",
    )
    elapsed = time.perf_counter() - started
    audit = _audit_decompose(result)
    return {
        "elapsed_seconds": round(elapsed, 3),
        "model": route_ctx.model,
        "thinking_helper_off": stream_enable_thinking(route_ctx.model) is False,
        "result": result,
        "audit": audit,
    }


async def run_decompose_stream(question: str) -> dict[str, Any]:
    """Streaming mentor decompose; collect SSE-like events."""
    route_ctx = route("mentor_decompose", has_image=False)
    service = MentorService()
    events: list[dict[str, Any]] = []
    preview_chars = 0
    first_preview_at: float | None = None
    complete_payload: dict[str, Any] | None = None
    error_message: str | None = None
    started = time.perf_counter()
    async for item in service.decompose_stream(
        MentorDecomposeInput(question=question),
        user_id=None,
        organization_id=None,
        endpoint_path="/smoke/maite/e2e/decompose/stream",
    ):
        event_name = str(item.get("event") or "")
        raw_data = item.get("data")
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
        events.append({"event": event_name, "keys": sorted(data.keys())})
        if event_name == "preview":
            text = str(data.get("text") or "")
            preview_chars += len(text)
            if first_preview_at is None:
                first_preview_at = time.perf_counter() - started
        elif event_name == "complete":
            complete_payload = data
        elif event_name == "error":
            error_message = str(data.get("message") or "stream error")
    elapsed = time.perf_counter() - started
    audit = _audit_decompose(complete_payload or {})
    return {
        "elapsed_seconds": round(elapsed, 3),
        "model": route_ctx.model,
        "thinking_helper_off": stream_enable_thinking(route_ctx.model) is False,
        "event_types": [item["event"] for item in events],
        "preview_chars": preview_chars,
        "first_preview_seconds": None if first_preview_at is None else round(first_preview_at, 3),
        "error_message": error_message,
        "result": complete_payload,
        "audit": audit,
        "pass": complete_payload is not None and audit["pass"] and error_message is None,
    }


async def main() -> None:
    """Run OCR + decompose e2e audit against one screenshot."""
    parser = argparse.ArgumentParser(description="Maite OCR + decompose e2e smoke")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument(
        "--skip-stream",
        action="store_true",
        help="Skip streaming decompose (complete only)",
    )
    parser.add_argument(
        "--keep-rate-limit",
        action="store_true",
        help="Keep DashScope rate limiting (default: disable for smoke reliability)",
    )
    args = parser.parse_args()
    image_path = args.image.resolve()
    if not image_path.is_file():
        raise SystemExit(f"Image not found: {image_path}")

    load_dotenv(ROOT / ".env")
    if not args.keep_rate_limit:
        os.environ["DASHSCOPE_RATE_LIMITING_ENABLED"] = "false"
    if not os.getenv("QWEN_API_KEY"):
        raise SystemExit("QWEN_API_KEY missing")
    if not init_redis_sync():
        raise SystemExit("Redis unavailable — start Redis or check REDIS_URL")
    llm_service.initialize()
    models = llm_service.client_manager.get_available_models()
    for required in ("qwen3.7-flash", "qwen3.7-plus"):
        if required not in models:
            raise SystemExit(f"{required} not registered in ClientManager")
    if llm_service.rate_limiter is not None and not args.keep_rate_limit:
        llm_service.rate_limiter.enabled = False

    report: dict[str, Any] = {
        "image": str(image_path),
        "image_bytes": image_path.stat().st_size,
        "steps": {},
        "overall_pass": False,
    }

    print("=" * 72)
    print(f"IMAGE: {image_path} ({report['image_bytes']} bytes)")
    print("STEP 1/3: OCR")
    ocr = await run_ocr(image_path)
    report["steps"]["ocr"] = ocr
    print(
        f"  model={ocr['model']} elapsed={ocr['elapsed_seconds']}s "
        f"chars={ocr['audit']['chars']} markers={ocr['audit']['markers_matched']}/"
        f"{ocr['audit']['markers_total']} pass={ocr['audit']['pass']}"
    )
    print("-" * 40)
    print((ocr.get("clean_text") or "")[:500])
    print("-" * 40)
    if not ocr["audit"]["pass"]:
        report["overall_pass"] = False
        _write_report(report)
        raise SystemExit("OCR audit failed")

    question = (ocr.get("clean_text") or ocr.get("raw_text") or "").strip()
    print("STEP 2/3: mentor decompose (complete)")
    complete = await run_decompose_complete(question)
    report["steps"]["decompose_complete"] = complete
    print(
        f"  model={complete['model']} elapsed={complete['elapsed_seconds']}s "
        f"tables={complete['audit']['condition_rows']}/"
        f"{complete['audit']['step_rows']}/{complete['audit']['model_rows']} "
        f"pass={complete['audit']['pass']}"
    )
    print(f"  next_question: {complete['audit']['next_question_preview']}")
    if not complete["audit"]["pass"]:
        _write_report(report)
        raise SystemExit("Decompose complete audit failed")

    if args.skip_stream:
        report["overall_pass"] = True
        _write_report(report)
        print("SKIP stream; overall PASS")
        return

    print("STEP 3/3: mentor decompose (stream)")
    stream = await run_decompose_stream(question)
    report["steps"]["decompose_stream"] = stream
    print(
        f"  model={stream['model']} elapsed={stream['elapsed_seconds']}s "
        f"first_preview={stream['first_preview_seconds']}s "
        f"preview_chars={stream['preview_chars']} "
        f"events={stream['event_types']} pass={stream['pass']}"
    )
    if stream.get("error_message"):
        print(f"  error: {stream['error_message']}")

    report["overall_pass"] = bool(
        ocr["audit"]["pass"]
        and complete["audit"]["pass"]
        and stream["pass"]
        and ocr["thinking_helper_off"]
        and complete["thinking_helper_off"]
        and stream["thinking_helper_off"]
    )
    _write_report(report)
    print("=" * 72)
    print(f"OVERALL: {'PASS' if report['overall_pass'] else 'FAIL'}")
    if not report["overall_pass"]:
        raise SystemExit(1)


def _write_report(report: dict[str, Any]) -> None:
    out = ROOT / "tmp" / "maite_e2e_smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE: {out}")


if __name__ == "__main__":
    asyncio.run(main())
