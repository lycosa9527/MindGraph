"""Smoke: extract teaching-design DOCX text then draft showcase AI copy.

Usage (WSL, from repo root):
  conda activate python313
  PYTHONPATH=. python scripts/smoke_showcase_ai_copy.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from services.showcase.ai_copy import (
    SHOWCASE_AI_COPY_MODEL,
    extract_document_text,
    generate_teaching_design_copy,
)

ROOT = Path(__file__).resolve().parents[1]

CASES = [
    {
        "path": Path("/mnt/c/Users/roywa/Desktop/【3.0版本】2402-《阿Q正传》教学设计-陈玉华.docx"),
        "title": "《阿Q正传》教学设计",
        "subject": "语文",
        "grade": "高中",
    },
    {
        "path": Path("/mnt/c/Users/roywa/Desktop/小学-六年级-语文-《两小儿辩日》-梁静-北京师范大学昌平附属学校4.docx"),
        "title": "《两小儿辩日》教学设计",
        "subject": "语文",
        "grade": "六年级",
    },
]


async def run_one(case: dict) -> dict:
    """Run extract + LLM for one fixture."""
    path: Path = case["path"]
    print("=" * 72)
    print(f"FILE: {path.name}")
    if not path.is_file():
        raise FileNotFoundError(path)
    print(f"SIZE: {path.stat().st_size} bytes")
    print(f"MODEL: {SHOWCASE_AI_COPY_MODEL}")
    text = extract_document_text(str(path))
    print(f"EXTRACTED_CHARS: {len(text)}")
    preview = text[:400].replace("\n", " ")
    print(f"EXTRACT_PREVIEW:\n{preview}")
    print("-" * 72)
    fields = await generate_teaching_design_copy(
        document_text=text,
        title=case["title"],
        subject=case["subject"],
        grade=case["grade"],
        user_id=None,
        organization_id=None,
        endpoint_path="/smoke/showcase/ai/teaching-copy",
    )
    per_field = {key: len(value) for key, value in fields.items()}
    total_chars = sum(per_field.values())
    print("RESULT_JSON:")
    print(json.dumps(fields, ensure_ascii=False, indent=2))
    print(f"PER_FIELD_CHARS: {json.dumps(per_field, ensure_ascii=False)}")
    print(f"TOTAL_FIELD_CHARS: {total_chars}")
    print()
    return {
        "file": path.name,
        "extracted_chars": len(text),
        "fields": fields,
        "per_field_chars": per_field,
        "total_field_chars": total_chars,
    }


async def main() -> None:
    """Run both Desktop teaching-design fixtures."""
    load_dotenv(ROOT / ".env")
    if not os.getenv("QWEN_API_KEY"):
        raise SystemExit("QWEN_API_KEY missing")
    if not init_redis_sync():
        raise SystemExit("Redis unavailable — start Redis or check REDIS_URL")
    llm_service.initialize()
    results = [await run_one(case) for case in CASES]
    out = ROOT / ".tmp_showcase_ai_copy_smoke.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE: {out}")


if __name__ == "__main__":
    asyncio.run(main())
