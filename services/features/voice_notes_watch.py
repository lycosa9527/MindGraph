"""Watch Voice Notes finish: save transcript and optionally generate a mind map."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request

from agents.mind_maps.web_content_mind_map_agent import WebContentMindMapAgent
from models.domain.auth import User
from services.features.voice_notes_markdown import (
    strip_voice_notes_markdown_meta,
    wrap_voice_notes_markdown,
)
from services.knowledge.doc_summary_ingest import DocSummaryIngestService
from services.knowledge.doc_summary_limits import (
    DOC_SUMMARY_MAX_INPUT_CHARS,
    content_exceeds_model_input,
)
from services.knowledge.knowledge_package_service import KnowledgePackageService
from services.monitoring.module_activity import schedule_module_activity
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from utils.auth.school_tier import max_diagrams_for_user
from utils.db.session_open import actor_rls_session

WATCH_FINISH_ENDPOINT = "/api/voice-notes/watch/finish"


@dataclass(frozen=True)
class VoiceNotesWatchFinish:
    """Small watch response: library id only, never the generated spec."""

    diagram_id: str
    title: str
    generated: bool


def blank_watch_mindmap_spec() -> dict[str, Any]:
    """Placeholder mind map so the library row exists before generate."""
    children: list[dict[str, Any]] = []
    for branch in range(1, 5):
        kids = []
        for child in range(1, 3):
            label = f"子项{branch}.{child}"
            kids.append({"label": label, "text": label, "children": []})
        branch_label = f"分支{branch}"
        children.append({"label": branch_label, "text": branch_label, "children": kids})
    return {
        "topic": "中心主题",
        "children": children,
        "_mindmap_theme": "rainbow",
        "_mindmap_diagram_style": "classic",
    }


def default_watch_title(now: Optional[datetime] = None) -> str:
    """Same stamp shape as the mobile Voice Notes title."""
    stamp = now or datetime.now(timezone.utc).astimezone()
    return stamp.strftime("voice recording_%Y%m%d%H%M")


def normalize_watch_transcript(raw: str) -> str:
    """Strip Voice Notes meta and clamp to the Document Summary budget."""
    text = strip_voice_notes_markdown_meta(raw).strip()
    if len(text) > DOC_SUMMARY_MAX_INPUT_CHARS:
        return text[:DOC_SUMMARY_MAX_INPUT_CHARS]
    return text


def _http_request_id(request: Request) -> Optional[str]:
    raw = request.headers.get("X-Request-Id")
    if raw is None:
        return None
    clipped = raw.strip()[:80]
    return clipped or None


async def _ensure_diagram(
    user: User,
    title: str,
    diagram_id: str,
) -> tuple[str, str]:
    cache = get_diagram_cache()
    if diagram_id:
        existing = await cache.get_diagram(user.id, diagram_id)
        if existing is None:
            raise ValueError("Diagram not found")
        stored_title = str(existing.get("title") or title)
        return str(existing["id"]), stored_title

    async with actor_rls_session(user) as db:
        diagram_cap = await max_diagrams_for_user(db, user)
    success, created_id, error = await cache.save_diagram(
        user_id=user.id,
        diagram_id=None,
        title=title,
        diagram_type="mindmap",
        spec=blank_watch_mindmap_spec(),
        language="zh",
        thumbnail=None,
        max_per_user=diagram_cap,
        organization_id=getattr(user, "organization_id", None),
        source_channel="voice_notes",
    )
    if not success or not created_id:
        raise ValueError(error or "Failed to create diagram")
    return created_id, title


async def _ingest_transcript(user: User, diagram_id: str, title: str, transcript: str) -> None:
    async with actor_rls_session(user) as db:
        packages = KnowledgePackageService(db, user.id)
        package = await packages.ensure_doc_summary_session(
            diagram_id=diagram_id,
            diagram_title=title,
            create_if_missing=True,
        )
        ingest = DocSummaryIngestService(db, user.id)
        await ingest.ingest_text(
            int(package.id),
            content=wrap_voice_notes_markdown(transcript),
            title=title,
            source_kind="voice_notes",
            language="zh",
        )


async def _generate_and_persist(
    user: User,
    request: Request,
    diagram_id: str,
    title: str,
    transcript: str,
) -> None:
    agent = WebContentMindMapAgent(model="qwen")
    result = await agent.generate_from_page_content(
        page_content=transcript,
        language="zh",
        content_format="text/markdown",
        page_title=title,
        page_url=None,
        user_id=user.id,
        organization_id=getattr(user, "organization_id", None),
        request_type="diagram_generation",
        endpoint_path=WATCH_FINISH_ENDPOINT,
        http_request_id=_http_request_id(request),
        source_kind="document",
    )
    if not result.get("success") or not isinstance(result.get("spec"), dict):
        raise RuntimeError(str(result.get("error") or "Generation failed"))
    cache = get_diagram_cache()
    existing = await cache.get_diagram(user.id, diagram_id)
    if existing is None:
        raise ValueError("Diagram not found")
    success, _, error = await cache.save_diagram(
        user_id=user.id,
        diagram_id=diagram_id,
        title=existing.get("title") or title,
        diagram_type=existing.get("diagram_type") or "mindmap",
        spec=result["spec"],
        language=existing.get("language") or "zh",
        thumbnail=existing.get("thumbnail"),
        organization_id=getattr(user, "organization_id", None),
        source_channel="voice_notes",
    )
    if not success:
        raise RuntimeError(error or "Failed to save generated mind map")


async def finish_watch_voice_note(
    user: User,
    request: Request,
    transcript: str,
    title: str = "",
    generate: bool = False,
    diagram_id: str = "",
) -> VoiceNotesWatchFinish:
    """Ingest watch transcript; optionally generate and persist a mind map."""
    text = normalize_watch_transcript(transcript)
    if not text:
        raise ValueError("Transcript is empty")
    if content_exceeds_model_input(len(text)) and generate:
        raise ValueError("Transcript exceeds model input limit")

    stored_title = title.strip() or default_watch_title()
    saved_id, stored_title = await _ensure_diagram(user, stored_title, diagram_id.strip())
    await _ingest_transcript(user, saved_id, stored_title, text)
    schedule_module_activity(
        user=user,
        module="voice_notes",
        redis_activity_type="voice_notes",
        request=request,
        details={"endpoint": "voice_notes_watch_finish", "generate": generate},
        detail=f"watch_finish generate={int(generate)}",
        usage_source="mindgraph",
        usage_action="voice_notes_watch",
        title=stored_title,
        prompt_preview=text[:120],
        diagram_id=saved_id,
    )
    if not generate:
        return VoiceNotesWatchFinish(diagram_id=saved_id, title=stored_title, generated=False)

    await _generate_and_persist(user, request, saved_id, stored_title, text)
    return VoiceNotesWatchFinish(diagram_id=saved_id, title=stored_title, generated=True)


__all__ = [
    "WATCH_FINISH_ENDPOINT",
    "VoiceNotesWatchFinish",
    "blank_watch_mindmap_spec",
    "default_watch_title",
    "finish_watch_voice_note",
    "normalize_watch_transcript",
]
