"""Canvas node label translation API (DashScope Qwen classification / flash)."""

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from models.domain.auth import User
from models.requests.requests_canvas_translate import (
    CANVAS_TRANSLATE_LANGUAGE_NAMES_EN,
    TranslateDiagramLabelResult,
    TranslateDiagramLabelsRequest,
    TranslateDiagramLabelsResponse,
    TranslateNodeLabelRequest,
    TranslateNodeLabelResponse,
)
from services.infrastructure.http.error_handler import LLMServiceError
from services.llm import llm_service
from utils.auth import get_current_user_or_api_key, is_superadmin

from .diagram_generation import _query_diagram_ownership
from .helpers import check_endpoint_rate_limit, get_rate_limit_identifier

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

_OUTPUT_WHITESPACE_RE = re.compile(r"\s+")
_BATCH_CHUNK_SIZE = 40
_STREAM_CHUNK_SIZE = 8


def _chinese_script_extra_rules(ui_locale: Optional[str]) -> str:
    """Append output-script hints when translating to Chinese (target code is often zh)."""
    if not ui_locale:
        return ""
    if ui_locale in ("zh-tw", "zh-hant", "hk", "mo"):
        return (
            "\n- For Chinese text, use Traditional Chinese characters (繁體中文), not Simplified.\n"
        )
    if ui_locale == "zh":
        return "\n- For Chinese text, use Simplified Chinese characters (简体中文).\n"
    return ""


def _normalize_translated_text(raw: str) -> str:
    """Collapse whitespace to a single line suitable for node labels."""
    stripped = (raw or "").strip()
    if not stripped:
        return ""
    single_line = _OUTPUT_WHITESPACE_RE.sub(" ", stripped)
    return single_line[:4096]


def _coerce_llm_text(raw: object) -> str:
    if isinstance(raw, list):
        return str(raw[0]) if raw else ""
    return str(raw)


def _parse_translations_json(llm_text: str, expected_len: int) -> list[str]:
    text = llm_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    translations = data.get("translations")
    if not isinstance(translations, list):
        raise ValueError("missing translations array")
    if len(translations) != expected_len:
        raise ValueError("translations length mismatch")
    out: list[str] = []
    for item in translations:
        if not isinstance(item, str):
            raise ValueError("translation must be string")
        normalized = _normalize_translated_text(item)
        if not normalized:
            raise ValueError("empty translation")
        out.append(normalized)
    return out


async def _translate_unique_texts_chunk(
    texts: list[str],
    lang_name: str,
    *,
    user_id: Optional[int],
    organization_id: Optional[int],
    diagram_type: Optional[str],
    extra_rules: str = "",
    endpoint_path: str = "/api/canvas/translate_diagram_labels",
) -> list[str]:
    payload = json.dumps(texts, ensure_ascii=False)
    system_message = (
        "You translate diagram labels (node or relationship text). Output rules:\n"
        "- Respond with only a JSON object: {\"translations\": [\"...\", ...]}.\n"
        "- The translations array MUST have exactly the same length and order as the input JSON array.\n"
        "- Each element must be only the translated string.\n"
        "- No markdown fences, no explanations.\n"
        "- Preserve meaning. Keep proper nouns when commonly left untranslated.\n"
        "- Do not add prefixes.\n"
        f"- Target language: {lang_name}."
        f"{extra_rules}"
    )
    user_message = f"Translate each string in this JSON array (same order):\n{payload}"
    max_tokens = min(8192, max(384, 64 * len(texts) + 400))
    raw = await llm_service.chat(
        prompt=user_message,
        system_message=system_message,
        model="qwen-turbo",
        temperature=0.2,
        max_tokens=max_tokens,
        use_knowledge_base=False,
        skip_load_balancing=False,
        user_id=user_id,
        organization_id=organization_id,
        request_type="canvas_translate",
        diagram_type=diagram_type,
        endpoint_path=endpoint_path,
    )
    return _parse_translations_json(_coerce_llm_text(raw), len(texts))


def _diagram_ordered_unique_texts(req: TranslateDiagramLabelsRequest) -> list[str]:
    """Deduplicate label texts in first-seen order (same as batch endpoint)."""
    ordered_texts: list[str] = []
    seen_keys: set[str] = set()
    for item in req.items:
        key = item.text.strip()
        if key not in seen_keys:
            seen_keys.add(key)
            ordered_texts.append(key)
    return ordered_texts


def _ndjson_line(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n"


async def _translate_diagram_labels_ndjson(
    req: TranslateDiagramLabelsRequest,
    *,
    lang_name: str,
    script_rules: str,
    user_id: Optional[int],
    organization_id: Optional[int],
) -> AsyncIterator[bytes]:
    """
    Translate in small unique-text chunks; emit one NDJSON row per diagram item as chunks complete.
    """
    yield _ndjson_line({"event": "start", "total_items": len(req.items)})
    ordered_texts = _diagram_ordered_unique_texts(req)
    translation_for_text: dict[str, str] = {}
    try:
        for start in range(0, len(ordered_texts), _STREAM_CHUNK_SIZE):
            chunk = ordered_texts[start : start + _STREAM_CHUNK_SIZE]
            translated_part = await _translate_unique_texts_chunk(
                chunk,
                lang_name,
                user_id=user_id,
                organization_id=organization_id,
                diagram_type=req.diagram_type,
                extra_rules=script_rules,
                endpoint_path="/api/canvas/translate_diagram_labels_stream",
            )
            for original, translated in zip(chunk, translated_part, strict=True):
                translation_for_text[original] = translated
            chunk_set = set(chunk)
            for item in req.items:
                key = item.text.strip()
                if key not in chunk_set:
                    continue
                translated = translation_for_text.get(key, "")
                if not translated:
                    yield _ndjson_line({"event": "error", "detail": "Translation produced an empty result"})
                    return
                yield _ndjson_line(
                    {
                        "event": "item",
                        "item_id": item.item_id,
                        "item_kind": item.item_kind,
                        "translated_text": translated,
                    }
                )
        yield _ndjson_line({"event": "done"})
    except LLMServiceError as exc:
        logger.warning("canvas_translate stream LLM error: %s", exc)
        yield _ndjson_line({"event": "error", "detail": "Translation service temporarily unavailable"})
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("canvas_translate stream parse error: %s", exc)
        yield _ndjson_line({"event": "error", "detail": "Translation produced an invalid result"})
    except Exception as exc:
        logger.error("canvas_translate stream failed: %s", exc, exc_info=True)
        yield _ndjson_line({"event": "error", "detail": "Translation failed"})


async def _ownership_check_diagram_translate(
    diagram_id: Optional[str],
    current_user: Optional[User],
) -> None:
    if diagram_id and current_user:
        workshop_code, diagram_user_id = await _query_diagram_ownership(diagram_id)
        if workshop_code:
            if not is_superadmin(current_user) and diagram_user_id != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail=("Only the diagram owner can use AI generation during collaboration"),
                )


@router.post("/canvas/translate_node_label", response_model=TranslateNodeLabelResponse)
async def translate_node_label(
    req: TranslateNodeLabelRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
):
    """
    Translate a single diagram node label using Qwen classification (qwen3.6-flash via env).
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "canvas_translate_node_label",
        identifier,
        max_requests=60,
        window_seconds=60,
    )

    await _ownership_check_diagram_translate(req.diagram_id, current_user)

    lang_code = req.target_language
    lang_name = CANVAS_TRANSLATE_LANGUAGE_NAMES_EN.get(lang_code, lang_code)
    source_text = req.text.strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="text must not be empty")

    system_message = (
        "You translate text for a diagram node label. Rules:\n"
        "- Output only the translation in the target language. No quotes, markdown, or explanations.\n"
        "- Preserve meaning. Keep proper nouns when commonly left untranslated.\n"
        "- Do not add prefixes like 'Translation:'.\n"
        f"- Target language: {lang_name}."
    )
    user_message = f"Translate this label:\n{source_text}"

    user_id = current_user.id if current_user and hasattr(current_user, "id") else None
    organization_id = (
        getattr(current_user, "organization_id", None) if current_user and hasattr(current_user, "id") else None
    )

    try:
        raw = await llm_service.chat(
            prompt=user_message,
            system_message=system_message,
            model="qwen-turbo",
            temperature=0.2,
            max_tokens=512,
            use_knowledge_base=False,
            skip_load_balancing=False,
            user_id=user_id,
            organization_id=organization_id,
            request_type="canvas_translate",
            diagram_type=req.diagram_type,
            endpoint_path="/api/canvas/translate_node_label",
        )
    except LLMServiceError as exc:
        logger.warning("canvas_translate LLM error: %s", exc)
        raise HTTPException(status_code=503, detail="Translation service temporarily unavailable") from exc
    except Exception as exc:
        logger.error("canvas_translate failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="Translation failed") from exc

    if isinstance(raw, list):
        raw = raw[0] if raw else ""

    normalized = _normalize_translated_text(str(raw))
    if not normalized:
        raise HTTPException(status_code=502, detail="Translation produced an empty result")

    return TranslateNodeLabelResponse(translated_text=normalized)


@router.post("/canvas/translate_diagram_labels", response_model=TranslateDiagramLabelsResponse)
async def translate_diagram_labels(
    req: TranslateDiagramLabelsRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
):
    """
    Translate many diagram labels (node and connection text) in batched LLM calls.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "canvas_translate_diagram_labels",
        identifier,
        max_requests=15,
        window_seconds=60,
    )
    await _ownership_check_diagram_translate(req.diagram_id, current_user)

    lang_code = req.target_language
    lang_name = CANVAS_TRANSLATE_LANGUAGE_NAMES_EN.get(lang_code, lang_code)
    script_rules = _chinese_script_extra_rules(req.ui_locale)

    ordered_texts = _diagram_ordered_unique_texts(req)

    translation_for_text: dict[str, str] = {}
    user_id = current_user.id if current_user and hasattr(current_user, "id") else None
    organization_id = (
        getattr(current_user, "organization_id", None) if current_user and hasattr(current_user, "id") else None
    )

    try:
        for start in range(0, len(ordered_texts), _BATCH_CHUNK_SIZE):
            chunk = ordered_texts[start : start + _BATCH_CHUNK_SIZE]
            translated_part = await _translate_unique_texts_chunk(
                chunk,
                lang_name,
                user_id=user_id,
                organization_id=organization_id,
                diagram_type=req.diagram_type,
                extra_rules=script_rules,
            )
            for original, translated in zip(chunk, translated_part, strict=True):
                translation_for_text[original] = translated
    except LLMServiceError as exc:
        logger.warning("canvas_translate batch LLM error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Translation service temporarily unavailable",
        ) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("canvas_translate batch parse error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Translation produced an invalid result",
        ) from exc
    except Exception as exc:
        logger.error("canvas_translate batch failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="Translation failed") from exc

    results: list[TranslateDiagramLabelResult] = []
    for item in req.items:
        original = item.text.strip()
        translated = translation_for_text.get(original, "")
        if not translated:
            raise HTTPException(status_code=502, detail="Translation produced an empty result")
        results.append(
            TranslateDiagramLabelResult(
                item_id=item.item_id,
                translated_text=translated,
                item_kind=item.item_kind,
            )
        )

    return TranslateDiagramLabelsResponse(translations=results)


@router.post("/canvas/translate_diagram_labels_stream")
async def translate_diagram_labels_stream(
    req: TranslateDiagramLabelsRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
):
    """
    Stream translated labels as NDJSON (progressive UX): start, item rows, done.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "canvas_translate_diagram_labels_stream",
        identifier,
        max_requests=15,
        window_seconds=60,
    )
    await _ownership_check_diagram_translate(req.diagram_id, current_user)

    lang_code = req.target_language
    lang_name = CANVAS_TRANSLATE_LANGUAGE_NAMES_EN.get(lang_code, lang_code)
    script_rules = _chinese_script_extra_rules(req.ui_locale)

    user_id = current_user.id if current_user and hasattr(current_user, "id") else None
    organization_id = (
        getattr(current_user, "organization_id", None) if current_user and hasattr(current_user, "id") else None
    )

    return StreamingResponse(
        _translate_diagram_labels_ndjson(
            req,
            lang_name=lang_name,
            script_rules=script_rules,
            user_id=user_id,
            organization_id=organization_id,
        ),
        media_type="application/x-ndjson",
    )
