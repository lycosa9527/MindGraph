"""Watch Voice Notes HTTP: save transcript and generate a mind map."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from models.domain.auth import User
from services.features.voice_notes_watch import (
    WATCH_FINISH_ENDPOINT,
    finish_watch_voice_note,
)
from services.infrastructure.http.error_handler import LLMServiceError
from services.infrastructure.http.llm_http_errors import raise_http_for_llm_error
from services.knowledge.doc_summary_limits import (
    DocSummaryContentTooLongError,
    content_too_long_detail,
)
from services.utils.error_types import DATABASE_ERRORS, LLM_PIPELINE_ERRORS
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice-notes"])


class VoiceNotesWatchFinishRequest(BaseModel):
    """Watch finish body: transcript plus optional generate."""

    transcript: str = Field(..., min_length=1, max_length=900_000)
    title: str = Field(default="", max_length=120)
    generate: bool = False
    diagram_id: str = Field(default="", max_length=64)


@router.post("/voice-notes/watch/finish")
async def voice_notes_watch_finish(
    payload: VoiceNotesWatchFinishRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Ingest a watch transcript; optionally generate and persist a mind map."""
    try:
        result = await finish_watch_voice_note(
            current_user,
            request,
            transcript=payload.transcript,
            title=payload.title,
            generate=payload.generate,
            diagram_id=payload.diagram_id,
        )
    except DocSummaryContentTooLongError as exc:
        raise HTTPException(
            status_code=413,
            detail=content_too_long_detail(char_count=exc.char_count),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMServiceError as exc:
        raise_http_for_llm_error(exc)
    except LLM_PIPELINE_ERRORS as exc:
        logger.warning("[VoiceNotesWatch] finish failed user=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Watch voice note failed") from exc
    except DATABASE_ERRORS as exc:
        logger.error("[VoiceNotesWatch] database failed user=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc

    return {
        "ok": True,
        "diagram_id": result.diagram_id,
        "title": result.title,
        "generated": result.generated,
        "endpoint": WATCH_FINISH_ENDPOINT,
    }
