"""Prompt set A — call qwen3.7-plus to produce structural lesson JSON."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any, Optional

from config.settings import config
from services.llm import llm_service
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from services.zhihui.outline import MindMapBranchOutline, MindMapOutline
from services.zhihui.prompts.lesson_planner_prompts import (
    LESSON_PLANNER_BRANCH_REPAIR,
    LESSON_PLANNER_CLOSE_REPAIR,
    LESSON_PLANNER_OPEN_REPAIR,
    LESSON_PLANNER_SYSTEM,
    build_branch_planner_message,
    build_close_planner_message,
    build_open_planner_message,
)

logger = logging.getLogger(__name__)

DEFAULT_PLANNER_MODEL = "qwen3.7-plus"
# Per-phase call (open / one branch / close) — not the full deck.
DEFAULT_PLANNER_MAX_TOKENS = 2500

PlanningProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


def planner_model_id() -> str:
    """Resolve lesson planner model from env/settings."""
    raw = getattr(config, "ZHIHUI_LESSON_PLANNER_MODEL", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return DEFAULT_PLANNER_MODEL


def planner_max_tokens() -> int:
    """Resolve per-phase planner completion budget."""
    raw = getattr(config, "ZHIHUI_LESSON_PLANNER_MAX_TOKENS", None)
    try:
        value = int(raw) if raw is not None else DEFAULT_PLANNER_MAX_TOKENS
    except (TypeError, ValueError):
        return DEFAULT_PLANNER_MAX_TOKENS
    return value if value > 0 else DEFAULT_PLANNER_MAX_TOKENS


def _strip_code_fence(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned, count=1)
    return cleaned.strip()


def _looks_truncated_json(text: str) -> bool:
    """Heuristic: truncated LLM JSON often ends mid-string or with unbalanced braces."""
    cleaned = (text or "").rstrip()
    if not cleaned:
        return True
    if cleaned[-1] not in ("}", "]"):
        return True
    return cleaned.count("{") > cleaned.count("}") or cleaned.count("[") > cleaned.count("]")


def _loads_planner_json(raw: str) -> Any:
    cleaned = _strip_code_fence(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        if _looks_truncated_json(cleaned):
            raise json.JSONDecodeError(
                f"{exc.msg} (likely truncated lesson-plan JSON, chars={len(cleaned)})",
                exc.doc,
                exc.pos,
            ) from exc
        raise


def _batch_has_frames(batch: Any) -> bool:
    if not isinstance(batch, dict):
        return False
    frames = batch.get("frames")
    return isinstance(frames, list) and any(isinstance(frame, dict) for frame in frames)


def _extract_batches(data: dict[str, Any]) -> list[dict[str, Any]]:
    batches = data.get("batches")
    if isinstance(batches, list):
        return [batch for batch in batches if isinstance(batch, dict)]
    if _batch_has_frames(data):
        return [data]
    return []


def parse_lesson_plan_json(raw: str) -> dict[str, Any]:
    """Parse and lightly validate a full (or merged) planner JSON."""
    data = _loads_planner_json(raw)
    if not isinstance(data, dict):
        raise ValueError("Lesson plan root must be an object")
    batches = _extract_batches(data)
    if not batches:
        raise ValueError("Lesson plan missing batches")
    if not any(_batch_has_frames(batch) for batch in batches):
        raise ValueError("Lesson plan has no frames")
    if not str(data.get("style_seed") or "").strip():
        data["style_seed"] = "清新教育插画，柔和配色，统一扁平矢量风格"
    data["batches"] = batches
    return data


def parse_open_phase_json(raw: str) -> dict[str, Any]:
    """Parse open-phase JSON: style_seed + open batch."""
    plan = parse_lesson_plan_json(raw)
    open_batches = [
        batch for batch in plan["batches"] if str(batch.get("batch_role") or "").strip().lower() in {"", "open"}
    ]
    if not open_batches:
        open_batches = [plan["batches"][0]]
    for batch in open_batches:
        batch["batch_role"] = "open"
    return {
        "style_seed": str(plan.get("style_seed") or "").strip() or "清新教育插画，柔和配色，统一扁平矢量风格",
        "batches": open_batches[:1],
    }


def parse_develop_phase_json(raw: str, *, focus_branch: str) -> dict[str, Any]:
    """Parse one develop-branch JSON slice."""
    data = _loads_planner_json(raw)
    if not isinstance(data, dict):
        raise ValueError("Develop phase root must be an object")
    batches = _extract_batches(data)
    if not batches or not _batch_has_frames(batches[0]):
        raise ValueError("Develop phase missing frames")
    batch = dict(batches[0])
    batch["batch_role"] = "develop"
    focus = (focus_branch or "").strip()
    frames = batch.get("frames")
    if isinstance(frames, list) and focus:
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            if not str(frame.get("focus_branch") or "").strip():
                frame["focus_branch"] = focus
    return batch


def parse_close_phase_json(raw: str) -> dict[str, Any]:
    """Parse close-phase JSON slice."""
    data = _loads_planner_json(raw)
    if not isinstance(data, dict):
        raise ValueError("Close phase root must be an object")
    batches = _extract_batches(data)
    if not batches or not _batch_has_frames(batches[0]):
        raise ValueError("Close phase missing frames")
    batch = dict(batches[0])
    batch["batch_role"] = "close"
    return batch


def _normalize_branch_hint(hint: Any) -> str:
    return str(hint or "").strip().lower()


def _outline_branch_rank(outline: MindMapOutline, hint: Any) -> int:
    """Return outline index for a focus_branch hint, or a large sentinel if unknown."""
    normalized = _normalize_branch_hint(hint)
    if not normalized:
        return len(outline.branches) + 100
    for index, branch in enumerate(outline.branches):
        branch_id = (branch.id or "").strip().lower()
        text = (branch.text or "").strip().lower()
        if branch_id and branch_id == normalized:
            return index
        if text and text == normalized:
            return index
    for index, branch in enumerate(outline.branches):
        text = (branch.text or "").strip().lower()
        if not text:
            continue
        if normalized in text or text in normalized:
            return index
    return len(outline.branches) + 100


def _batch_branch_hints(batch: dict[str, Any]) -> list[str]:
    """All non-empty focus_branch values in frame order (deduped)."""
    frames = batch.get("frames")
    if not isinstance(frames, list):
        return []
    hints: list[str] = []
    seen: set[str] = set()
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        hint = str(frame.get("focus_branch") or "").strip()
        if not hint:
            continue
        key = hint.lower()
        if key in seen:
            continue
        seen.add(key)
        hints.append(hint)
    return hints


def _batch_sort_rank(outline: MindMapOutline, batch: dict[str, Any]) -> int:
    """
    Sort key for a develop batch: earliest outline branch among its focus_branches.

    Mixed-branch batches follow the first clockwise branch they cover.
    """
    hints = _batch_branch_hints(batch)
    if not hints:
        return len(outline.branches) + 100
    return min(_outline_branch_rank(outline, hint) for hint in hints)


def _develop_first_seen_order(batches: list[Any], outline: MindMapOutline) -> list[int]:
    """Outline ranks for develop batches in plan order (earliest branch each)."""
    ranks: list[int] = []
    seen: set[int] = set()
    for batch in batches:
        if not isinstance(batch, dict):
            continue
        role = str(batch.get("batch_role") or "").strip().lower()
        if role and role != "develop":
            continue
        rank = _batch_sort_rank(outline, batch)
        if rank >= len(outline.branches):
            continue
        if rank in seen:
            continue
        seen.add(rank)
        ranks.append(rank)
    return ranks


def _stable_sort_frames_by_branch(batch: dict[str, Any], outline: MindMapOutline) -> bool:
    """
    Stable-sort frames in a develop batch by outline branch rank.

    Keeps relative order within the same branch (intro → children → conflict).
    Returns True when the frame list changed.
    """
    frames = batch.get("frames")
    if not isinstance(frames, list) or len(frames) <= 1:
        return False

    indexed = list(enumerate(frames))
    indexed.sort(
        key=lambda item: (
            _outline_branch_rank(
                outline,
                item[1].get("focus_branch") if isinstance(item[1], dict) else "",
            ),
            item[0],
        )
    )
    new_frames = [frame for _, frame in indexed]
    if new_frames == frames:
        return False
    batch["frames"] = new_frames
    return True


def develop_branch_first_seen_texts(
    plan: dict[str, Any],
    outline: MindMapOutline,
) -> list[str]:
    """Clockwise-facing develop branch texts in first-seen slide order."""
    batches = plan.get("batches")
    if not isinstance(batches, list) or not outline.branches:
        return []
    texts: list[str] = []
    seen: set[int] = set()
    for batch in batches:
        if not isinstance(batch, dict):
            continue
        role = str(batch.get("batch_role") or "").strip().lower()
        if role and role not in {"develop", ""}:
            continue
        frames = batch.get("frames")
        if not isinstance(frames, list):
            continue
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            rank = _outline_branch_rank(outline, frame.get("focus_branch"))
            if rank >= len(outline.branches) or rank in seen:
                continue
            seen.add(rank)
            texts.append(outline.branches[rank].text)
    return texts


def normalize_lesson_plan_to_outline(
    plan: dict[str, Any],
    outline: MindMapOutline,
) -> dict[str, Any]:
    """
    Align lesson-plan batches/frames to outline clockwise order.

    - Permute develop batches to outline order (open/close kept).
    - Stable-sort frames inside each develop batch by branch rank.
    """
    batches = plan.get("batches")
    if not isinstance(batches, list) or not batches or not outline.branches:
        return plan

    open_batches: list[dict[str, Any]] = []
    develop_batches: list[dict[str, Any]] = []
    close_batches: list[dict[str, Any]] = []
    other_batches: list[dict[str, Any]] = []

    for batch in batches:
        if not isinstance(batch, dict):
            continue
        role = str(batch.get("batch_role") or "").strip().lower()
        if role == "open":
            open_batches.append(batch)
        elif role == "close":
            close_batches.append(batch)
        elif role == "develop" or not role:
            develop_batches.append(batch)
        else:
            other_batches.append(batch)

    before = _develop_first_seen_order(batches, outline)
    expected = list(range(len(outline.branches)))
    expected_present = [rank for rank in expected if rank in before]
    reordered_batches = False
    if len(develop_batches) > 1 and before != expected_present:
        indexed = list(enumerate(develop_batches))
        indexed.sort(
            key=lambda item: (
                _batch_sort_rank(outline, item[1]),
                item[0],
            )
        )
        develop_batches = [batch for _, batch in indexed]
        reordered_batches = True

    frames_fixed = False
    for batch in develop_batches:
        if _stable_sort_frames_by_branch(batch, outline):
            frames_fixed = True

    plan["batches"] = open_batches + other_batches + develop_batches + close_batches
    after = _develop_first_seen_order(plan["batches"], outline)
    if reordered_batches or frames_fixed:
        logger.warning(
            "[ZhiHui] Normalized lesson plan to outline clockwise "
            "reordered_batches=%s frames_fixed=%s before=%s after=%s outline=%s",
            reordered_batches,
            frames_fixed,
            before,
            after,
            [branch.text for branch in outline.branches],
        )
    elif after != expected_present:
        logger.warning(
            "[ZhiHui] Develop branch order still mismatched after normalize got=%s expected=%s outline=%s",
            after,
            expected_present,
            [branch.text for branch in outline.branches],
        )
    return plan


def reorder_develop_batches_to_outline(
    plan: dict[str, Any],
    outline: MindMapOutline,
) -> dict[str, Any]:
    """Backward-compatible alias for ``normalize_lesson_plan_to_outline``."""
    return normalize_lesson_plan_to_outline(plan, outline)


def _merge_usage(
    total: Optional[dict[str, Any]],
    part: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    if not isinstance(part, dict):
        return total
    if total is None:
        return dict(part)
    merged = dict(total)
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
        left = merged.get(key) or 0
        right = part.get(key) or 0
        try:
            merged[key] = int(left) + int(right)
        except (TypeError, ValueError):
            continue
    return merged


def _branch_payload(branch: MindMapBranchOutline) -> dict[str, Any]:
    return {
        "id": branch.id,
        "text": branch.text,
        "children": list(branch.children),
    }


async def _chat_phase(
    *,
    prompt: str,
    repair_suffix: str,
    model: str,
    max_tokens: int,
    temperature: float,
    user_id: Optional[int],
    organization_id: Optional[int],
    parse_fn: Callable[[str], Any],
    phase_label: str,
) -> tuple[Any, Optional[dict[str, Any]]]:
    response = ""
    usage: Optional[dict[str, Any]] = None
    try:
        response, usage = await llm_service.chat_with_usage(
            prompt=prompt,
            model=model,
            system_message=LESSON_PLANNER_SYSTEM,
            max_tokens=max_tokens,
            temperature=temperature,
            user_id=user_id,
            organization_id=organization_id,
        )
        return parse_fn(response or ""), usage
    except (json.JSONDecodeError, ValueError, TypeError) as first_exc:
        logger.warning(
            "[ZhiHui] Lesson plan %s parse failed chars=%s max_tokens=%s err=%s; retrying",
            phase_label,
            len(response or ""),
            max_tokens,
            first_exc,
        )
        try:
            response, usage = await llm_service.chat_with_usage(
                prompt=f"{prompt}\n\n{repair_suffix}",
                model=model,
                system_message=LESSON_PLANNER_SYSTEM,
                max_tokens=max_tokens,
                temperature=0.2,
                user_id=user_id,
                organization_id=organization_id,
            )
            return parse_fn(response or ""), usage
        except (json.JSONDecodeError, ValueError, TypeError, *BACKGROUND_INFRA_ERRORS) as exc:
            raise ValueError(f"Lesson planner failed ({phase_label}): {exc}") from exc
    except BACKGROUND_INFRA_ERRORS as exc:
        raise ValueError(f"Lesson planner failed ({phase_label}): {exc}") from exc


async def plan_lesson_from_outline(
    outline: MindMapOutline,
    *,
    language: str = "zh",
    diagram_title: str = "",
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    on_progress: Optional[PlanningProgressCallback] = None,
) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    """
    Run branch-scoped lesson planner: open → each branch → close.

    Returns (plan_dict, aggregated_usage_data).
    """
    model = planner_model_id()
    max_tokens = planner_max_tokens()
    title = diagram_title or outline.topic
    outline_payload = outline.to_planner_payload()
    branch_total = len(outline.branches)
    usage_total: Optional[dict[str, Any]] = None

    async def _progress(payload: dict[str, Any]) -> None:
        if on_progress is None:
            return
        await on_progress(payload)

    await _progress(
        {
            "phase": "planning",
            "planning_stage": "open",
            "branch_index": 0,
            "branch_total": branch_total,
        }
    )
    open_plan, open_usage = await _chat_phase(
        prompt=build_open_planner_message(
            outline_payload,
            language=language,
            diagram_title=title,
        ),
        repair_suffix=LESSON_PLANNER_OPEN_REPAIR,
        model=model,
        max_tokens=max_tokens,
        temperature=0.4,
        user_id=user_id,
        organization_id=organization_id,
        parse_fn=parse_open_phase_json,
        phase_label="open",
    )
    usage_total = _merge_usage(usage_total, open_usage)
    style_seed = str(open_plan.get("style_seed") or "").strip()
    batches: list[dict[str, Any]] = list(open_plan.get("batches") or [])

    choice_index = max(0, branch_total // 2) if branch_total else 0
    for index, branch in enumerate(outline.branches):
        await _progress(
            {
                "phase": "planning",
                "planning_stage": "develop",
                "branch_index": index + 1,
                "branch_total": branch_total,
                "branch_text": branch.text,
            }
        )
        focus = (branch.id or branch.text or "").strip()
        develop_batch, branch_usage = await _chat_phase(
            prompt=build_branch_planner_message(
                outline_payload,
                _branch_payload(branch),
                style_seed=style_seed,
                branch_index=index + 1,
                branch_total=branch_total,
                language=language,
                diagram_title=title,
                include_choice_frame=index == choice_index,
            ),
            repair_suffix=LESSON_PLANNER_BRANCH_REPAIR,
            model=model,
            max_tokens=max_tokens,
            temperature=0.4,
            user_id=user_id,
            organization_id=organization_id,
            parse_fn=partial(parse_develop_phase_json, focus_branch=focus),
            phase_label=f"develop[{index + 1}/{branch_total}]",
        )
        usage_total = _merge_usage(usage_total, branch_usage)
        batches.append(develop_batch)

    await _progress(
        {
            "phase": "planning",
            "planning_stage": "close",
            "branch_index": branch_total,
            "branch_total": branch_total,
        }
    )
    close_batch, close_usage = await _chat_phase(
        prompt=build_close_planner_message(
            outline_payload,
            style_seed=style_seed,
            language=language,
            diagram_title=title,
        ),
        repair_suffix=LESSON_PLANNER_CLOSE_REPAIR,
        model=model,
        max_tokens=max_tokens,
        temperature=0.4,
        user_id=user_id,
        organization_id=organization_id,
        parse_fn=parse_close_phase_json,
        phase_label="close",
    )
    usage_total = _merge_usage(usage_total, close_usage)
    batches.append(close_batch)

    plan = {
        "style_seed": style_seed or "清新教育插画，柔和配色，统一扁平矢量风格",
        "batches": batches,
    }
    return normalize_lesson_plan_to_outline(plan, outline), usage_total
