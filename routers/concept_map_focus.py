"""
Concept map focus question API
==============================

Standard mode: **validation** (3 LLMs in parallel, once) and **suggestions** (3 LLMs,
separate batches, SSE as each model finishes). Models may disagree on valid — UI shows
per-model verdict. Suggestions paginate 5 per page on the client.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from models.domain.auth import User
from models.requests.requests_diagram import (
    FocusQuestionReviewRequest,
    FocusQuestionSuggestionsRequest,
)
from prompts import get_prompt
from services.llm import llm_service
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/concept_map", tags=["concept_map"])

FOCUS_MODELS: Tuple[str, ...] = ("qwen", "deepseek", "doubao")
FOCUS_SUGGESTION_COUNT = 5
FOCUS_REASON_MAX_LEN = 4000


def _sse_data(obj: Dict[str, Any]) -> str:
    """One SSE event line (UTF-8 safe for Chinese)."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _question_lang_or_raise(req: FocusQuestionReviewRequest) -> Tuple[str, str]:
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question required")
    return question, req.language


def _avoid_section(avoid: Optional[List[str]], lang: str) -> str:
    if not avoid:
        return ""
    lines = "\n".join(f"- {a}" for a in avoid[:50])
    if lang == "zh":
        return (
            "以下备选问题已在界面上出现过，请再给出 5 条**不同**的新备选"
            "（勿重复或仅微调同义重复）：\n"
            + lines
            + "\n"
        )
    return (
        "These alternatives were already shown; produce 5 **new** distinct options:\n"
        + lines
        + "\n"
    )


def _get_validate_prompts(lang: str) -> Tuple[str, str]:
    system = get_prompt("concept_map_focus_validate", lang, "system")
    user_tmpl = get_prompt("concept_map_focus_validate", lang, "user")
    if not system.strip() or not user_tmpl.strip():
        logger.error("[FocusQuestion] Missing validate prompts for language=%s", lang)
        raise HTTPException(status_code=500, detail="prompt_configuration_error")
    return system, user_tmpl


def _get_suggestions_prompts(lang: str) -> Tuple[str, str]:
    system = get_prompt("concept_map_focus_suggestions", lang, "system")
    user_tmpl = get_prompt("concept_map_focus_suggestions", lang, "user")
    if not system.strip() or not user_tmpl.strip():
        logger.error("[FocusQuestion] Missing suggestions prompts for language=%s", lang)
        raise HTTPException(status_code=500, detail="prompt_configuration_error")
    return system, user_tmpl


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        if len(lines) >= 2 and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _parse_json_object(raw: str) -> Dict[str, Any]:
    text = _strip_code_fence(raw)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no_json_object") from None
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("not_a_dict") from None
    return parsed


def _normalize_validate(parsed: Dict[str, Any]) -> Dict[str, Any]:
    reason = parsed.get("reason")
    text = str(reason).strip()[:FOCUS_REASON_MAX_LEN] if reason is not None else ""
    return {"valid": bool(parsed.get("valid")), "reason": text}


def _pad_suggestion(lang: str) -> str:
    if lang == "zh":
        return "请用一句完整问句描述概念图要回答的核心问题。"
    return "State one clear question your concept map should answer."


def _normalize_suggestions(parsed: Dict[str, Any], lang: str) -> List[str]:
    raw = parsed.get("suggestions")
    out: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    out.append(s)
    while len(out) < FOCUS_SUGGESTION_COUNT:
        out.append(_pad_suggestion(lang))
    return out[:FOCUS_SUGGESTION_COUNT]


async def _chat_completion(
    model: str,
    system: str,
    user: str,
    user_id: int,
    organization_id: Optional[int],
    endpoint_path: str,
    request_type: str,
    max_tokens: int,
) -> str:
    raw = await llm_service.chat(
        prompt=user,
        system_message=system,
        model=model,
        temperature=0.35,
        max_tokens=max_tokens,
        user_id=user_id,
        organization_id=organization_id,
        request_type=request_type,
        diagram_type="concept_map",
        endpoint_path=endpoint_path,
        use_knowledge_base=False,
        skip_load_balancing=False,
    )
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return str(raw)


async def _validate_one_model(
    model: str,
    question: str,
    lang: str,
    user_id: int,
    organization_id: Optional[int],
) -> Dict[str, Any]:
    system, user_tmpl = _get_validate_prompts(lang)
    user = user_tmpl.format(question=question)
    try:
        raw = await _chat_completion(
            model,
            system,
            user,
            user_id,
            organization_id,
            "/api/concept_map/focus_question_review/validate",
            "concept_map_focus_validate",
            2200,
        )
        if not raw.strip():
            raise ValueError("empty_response")
        parsed = _parse_json_object(raw)
        norm = _normalize_validate(parsed)
        return {
            "model": model,
            "valid": norm["valid"],
            "reason": norm["reason"],
            "error": None,
        }
    except Exception as exc:
        logger.warning("[FocusQuestion] validate model=%s: %s", model, exc)
        return {
            "model": model,
            "valid": False,
            "reason": "",
            "error": str(exc)[:500],
        }


async def _suggestions_for_model_task(
    model: str,
    question: str,
    lang: str,
    avoid: Optional[List[str]],
    user_id: int,
    organization_id: Optional[int],
) -> Dict[str, Any]:
    system, user_tmpl = _get_suggestions_prompts(lang)
    user = user_tmpl.format(
        question=question,
        avoid_section=_avoid_section(avoid, lang),
    )
    try:
        raw = await _chat_completion(
            model,
            system,
            user,
            user_id,
            organization_id,
            "/api/concept_map/focus_question_review/suggestions/stream",
            "concept_map_focus_suggestions",
            1600,
        )
        if not raw.strip():
            raise ValueError("empty_response")
        parsed = _parse_json_object(raw)
        suggestions = _normalize_suggestions(parsed, lang)
        return {
            "event": "model_suggestions",
            "model": model,
            "suggestions": suggestions,
        }
    except Exception as exc:
        logger.warning("[FocusQuestion] suggestions model=%s: %s", model, exc)
        return {
            "event": "model_error",
            "model": model,
            "message": str(exc)[:500],
        }


@router.post("/focus_question_review/validate")
async def focus_question_validate(
    req: FocusQuestionReviewRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Run Novak-style validation once per model (qwen, deepseek, doubao) in parallel.
    Models may disagree; each returns valid + reason.
    """
    question, lang = _question_lang_or_raise(req)
    user_id = current_user.id
    org_id = getattr(current_user, "organization_id", None)

    results = await asyncio.gather(
        *[
            _validate_one_model(m, question, lang, user_id, org_id)
            for m in FOCUS_MODELS
        ]
    )
    return JSONResponse({"results": list(results)})


@router.post("/focus_question_review/suggestions/stream")
async def focus_question_suggestions_stream(
    req: FocusQuestionSuggestionsRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Stream suggestion batches: each model completes independently (SSE event per model).

    Events:
    - ``model_suggestions``: {event, model, suggestions: [5 strings]}
    - ``model_error``: {event, model, message}
    - ``end``: batch wave finished
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question required")
    lang = req.language
    avoid = req.avoid
    user_id = current_user.id
    org_id = getattr(current_user, "organization_id", None)

    async def event_gen() -> AsyncIterator[str]:
        tasks = {
            asyncio.create_task(
                _suggestions_for_model_task(
                    m, question, lang, avoid, user_id, org_id
                )
            ): m
            for m in FOCUS_MODELS
        }
        try:
            while tasks:
                done, _ = await asyncio.wait(
                    tasks.keys(),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for finished in done:
                    _model = tasks.pop(finished)
                    try:
                        payload = await finished
                    except Exception as exc:
                        logger.error(
                            "[FocusQuestion] suggestions task %s: %s",
                            _model,
                            exc,
                            exc_info=True,
                        )
                        yield _sse_data(
                            {
                                "event": "model_error",
                                "model": _model,
                                "message": str(exc)[:500],
                            }
                        )
                        continue
                    yield _sse_data(payload)
            yield _sse_data({"event": "end"})
        except Exception as exc:
            logger.error("[FocusQuestion] suggestions stream: %s", exc, exc_info=True)
            yield _sse_data({"event": "error", "message": str(exc)[:500]})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
