"""Unified Kitty / one-sentence conversation image processing.

Classify with vision (thinking off): hand-drawn mind map → rebuild canvas +
markdown outline extract; otherwise OCR → Document Summary extract.md.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from agents.mind_maps.mind_map_agent import MindMapAgent
from services.knowledge.document_processor import DocumentProcessor
from services.knowledge.doc_summary_ingest import DocSummaryIngestService
from services.knowledge.knowledge_package_service import KnowledgePackageService
from services.knowledge.mindmap_outline_md import mindmap_spec_to_outline_markdown
from services.knowledge.vision_mindmap import (
    VISION_MINDMAP_CALL_ERRORS,
    detect_and_rebuild_mindmap_from_image,
)
from services.knowledge.vision_mindmap_apply import apply_rebuilt_mindmap_to_library
from services.utils.error_types import DATABASE_ERRORS, FILE_IO_ERRORS, REDIS_ERRORS
from utils.db.session_open import user_rls_session

logger = logging.getLogger(__name__)

_PERSIST_ERRORS: tuple[type[BaseException], ...] = (
    ValueError,
    RuntimeError,
    *DATABASE_ERRORS,
    *REDIS_ERRORS,
    *FILE_IO_ERRORS,
)

OCR_EXCERPT_CHARS = 480


async def process_conversation_image(
    *,
    user_id: int,
    organization_id: Optional[int],
    image_bytes: bytes,
    mime_type: str,
    filename: str,
    language: str,
    diagram_id: str,
    diagram_title: Optional[str] = None,
    apply_to_library: bool = True,
) -> Dict[str, Any]:
    """Classify image and persist extract; optionally rebuild a hand-drawn map.

    Returns a JSON-serializable result with ``mode`` ``handdrawn`` | ``text``.
    """
    diagram_id = (diagram_id or "").strip()
    if not diagram_id:
        raise ValueError("diagram_id is required")
    if not image_bytes:
        raise ValueError("Empty image")

    page_title = (filename or "Image").strip()[:200] or "Image"
    language = (language or "zh").strip() or "zh"

    vision = None
    try:
        vision = await detect_and_rebuild_mindmap_from_image(
            image_bytes,
            mime_type=mime_type,
            language=language,
        )
    except VISION_MINDMAP_CALL_ERRORS as exc:
        logger.warning(
            "[ConversationImage] vision detect failed user=%s: %s",
            user_id,
            exc,
        )

    if vision is not None and vision.is_mindmap and vision.spec is not None:
        agent = MindMapAgent(model="qwen")
        is_valid, validation_msg = agent.validate_output(vision.spec)
        if is_valid:
            enhanced = await agent.enhance_spec(vision.spec)
            if isinstance(enhanced, dict) and enhanced.get("topic"):
                outline = mindmap_spec_to_outline_markdown(enhanced)
                package_id = await _persist_doc_summary_markdown(
                    user_id=user_id,
                    diagram_id=diagram_id,
                    diagram_title=diagram_title or page_title,
                    markdown=outline,
                    title=f"{page_title} (hand-drawn)",
                    language=language,
                    source_kind="handdrawn_mindmap",
                    extra_metadata={
                        "vision_source": "handdrawn",
                        "confidence": vision.confidence,
                    },
                )
                if package_id is None:
                    raise RuntimeError("Failed to save hand-drawn outline to Document Summary")
                library: Dict[str, Any] = {}
                if apply_to_library:
                    library = await apply_rebuilt_mindmap_to_library(
                        user_id=user_id,
                        diagram_id=diagram_id,
                        spec=enhanced,
                        language=language,
                        title=diagram_title or page_title,
                        organization_id=organization_id,
                    )
                topic = str(enhanced.get("topic") or "").strip()
                return {
                    "success": True,
                    "mode": "handdrawn",
                    "is_mindmap": True,
                    "confidence": vision.confidence,
                    "reason": vision.reason,
                    "spec": enhanced,
                    "diagram_type": agent.diagram_type,
                    "topic": topic,
                    "package_id": package_id,
                    "doc_summary_saved": True,
                    "library": library,
                    "outline_markdown": outline,
                    "reply_key": "handdrawn",
                }
            logger.warning(
                "[ConversationImage] enhance_spec invalid user=%s",
                user_id,
            )
        else:
            logger.warning(
                "[ConversationImage] rebuilt spec invalid user=%s: %s",
                user_id,
                validation_msg,
            )

    ocr_text = _ocr_image_bytes(image_bytes, mime_type=mime_type, filename=filename)
    if not ocr_text:
        raise ValueError("No text extracted from image")

    package_id = await _persist_doc_summary_markdown(
        user_id=user_id,
        diagram_id=diagram_id,
        diagram_title=diagram_title or page_title,
        markdown=ocr_text,
        title=page_title,
        language=language,
        source_kind="image_ocr",
        extra_metadata={"vision_source": "ocr"},
    )
    if package_id is None:
        raise RuntimeError("Failed to save OCR extract to Document Summary")
    excerpt = ocr_text[:OCR_EXCERPT_CHARS].strip()
    if len(ocr_text) > OCR_EXCERPT_CHARS:
        excerpt = excerpt.rstrip() + "…"
    return {
        "success": True,
        "mode": "text",
        "is_mindmap": False,
        "confidence": vision.confidence if vision is not None else 0.0,
        "reason": vision.reason if vision is not None else "ocr",
        "package_id": package_id,
        "doc_summary_saved": True,
        "ocr_text": ocr_text,
        "ocr_excerpt": excerpt,
        "reply_key": "text",
    }


def _ocr_image_bytes(image_bytes: bytes, *, mime_type: str, filename: str) -> str:
    """OCR via DocumentProcessor temp file."""
    suffix = Path(filename or "upload.jpg").suffix or ".jpg"
    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(image_bytes)
            temp_path = Path(tmp.name)
        processor = DocumentProcessor()
        extracted = processor.extract_text(str(temp_path), mime_type)
        return (extracted or "").strip()
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)


async def _persist_doc_summary_markdown(
    *,
    user_id: int,
    diagram_id: str,
    diagram_title: str,
    markdown: str,
    title: str,
    language: str,
    source_kind: str,
    extra_metadata: Optional[dict] = None,
) -> Optional[int]:
    """Ensure Doc Summary session and store markdown extract."""
    try:
        async with user_rls_session(user_id) as db:
            packages = KnowledgePackageService(db, user_id)
            package = await packages.ensure_doc_summary_session(
                diagram_id=diagram_id,
                diagram_title=diagram_title,
                create_if_missing=True,
            )
            ingest = DocSummaryIngestService(db, user_id)
            await ingest.ingest_text(
                package_id=package.id,
                content=markdown,
                title=title,
                source_kind=source_kind,
                language=language,
                extra_metadata=extra_metadata,
            )
            return int(package.id)
    except _PERSIST_ERRORS as exc:
        logger.warning(
            "[ConversationImage] doc_summary persist failed user=%s diagram=%s: %s",
            user_id,
            diagram_id,
            exc,
        )
        return None
