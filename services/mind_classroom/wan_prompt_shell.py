"""Merge lesson-plan frames into Wan 组图 prompts (prompt set B)."""

from __future__ import annotations

import logging
from typing import Any

from services.t2i.wan_image_client import WAN_MAX_N, clamp_wan_n
from services.mind_classroom.prompts.wan_image_shell import WAN_IMAGE_SHELL

logger = logging.getLogger(__name__)

# DashScope Wan: each CJK / letter / digit / symbol counts as 1 character.
WAN_PROMPT_MAX_CHARS = 5000


def _focus_branch_key(frame: dict[str, Any]) -> str:
    return str(frame.get("focus_branch") or "").strip().lower()


def _frame_line(index: int, frame: dict[str, Any]) -> str:
    title = str(frame.get("title") or "").strip() or f"第{index}帧"
    role = str(frame.get("frame_role") or "").strip()
    beat = str(frame.get("lesson_beat") or "").strip()
    learning = str(frame.get("learning_point") or "").strip()
    manifestation = str(frame.get("manifestation") or "").strip()
    think = str(frame.get("think_prompt") or "").strip()
    conflict = frame.get("cognitive_conflict") is True
    subjects = frame.get("visual_subjects") or []
    if isinstance(subjects, list):
        subject_text = "、".join(str(item).strip() for item in subjects if str(item).strip())
    else:
        subject_text = str(subjects).strip()
    parts = [f"第{index}张：{title}"]
    if role:
        parts.append(f"分镜角色：{role}")
    if conflict or role == "cognitive_conflict":
        parts.append("认知冲突高亮页：并置对立/误解，画面有思考张力")
    if beat:
        parts.append(beat)
    if learning:
        parts.append(f"学习要点：{learning}")
    if manifestation:
        parts.append(f"直接具象：{manifestation}")
    if think:
        parts.append(f"思考问句：{think}")
    if subject_text:
        parts.append(f"画面主体：{subject_text}")
    return "；".join(parts)


def _compose_wan_prompt_text(
    *,
    style_seed: str,
    frames: list[dict[str, Any]],
    batch_role: str = "",
) -> str:
    """Compose Wan prompt text without applying the API char cap."""
    lines = [WAN_IMAGE_SHELL.strip()]
    seed = (style_seed or "").strip()
    if seed:
        lines.append(f"统一风格：{seed}")
    role = (batch_role or "").strip()
    if role:
        lines.append(f"本批课程位置：{role}")
    for index, frame in enumerate(frames, start=1):
        if isinstance(frame, dict):
            lines.append(_frame_line(index, frame))
    return "\n".join(lines).strip()


def build_wan_batch_prompt(
    *,
    style_seed: str,
    frames: list[dict[str, Any]],
    batch_role: str = "",
    max_chars: int = WAN_PROMPT_MAX_CHARS,
) -> str:
    """Compose one Wan 组图 text from shell + style + frames."""
    text = _compose_wan_prompt_text(
        style_seed=style_seed,
        frames=frames,
        batch_role=batch_role,
    )
    if len(text) <= max_chars:
        return text
    logger.warning(
        "[ZhiHui] Wan prompt still over limit after packing chars=%s max=%s frames=%s; truncating",
        len(text),
        max_chars,
        len(frames),
    )
    return text[:max_chars]


def _prompt_len(
    *,
    style_seed: str,
    batch_role: str,
    frames: list[dict[str, Any]],
) -> int:
    return len(
        _compose_wan_prompt_text(
            style_seed=style_seed,
            frames=frames,
            batch_role=batch_role,
        )
    )


def _compact_frame_fields(frame: dict[str, Any], *, budget: int) -> dict[str, Any]:
    """Shorten verbose fields so a single frame can fit under the char budget."""
    compacted = dict(frame)
    for key in ("manifestation", "lesson_beat", "learning_point", "think_prompt"):
        value = str(compacted.get(key) or "").strip()
        if len(value) > budget:
            compacted[key] = value[: max(0, budget)]
    subjects = compacted.get("visual_subjects")
    if isinstance(subjects, list) and len(subjects) > 3:
        compacted["visual_subjects"] = subjects[:3]
    return compacted


def _fit_single_frame(
    frame: dict[str, Any],
    *,
    style_seed: str,
    batch_role: str,
    max_chars: int,
) -> dict[str, Any]:
    """Ensure shell + one frame fits in max_chars; compact then rely on final truncate."""
    if _prompt_len(style_seed=style_seed, batch_role=batch_role, frames=[frame]) <= max_chars:
        return frame
    for budget in (400, 200, 80, 40):
        candidate = _compact_frame_fields(frame, budget=budget)
        if _prompt_len(style_seed=style_seed, batch_role=batch_role, frames=[candidate]) <= max_chars:
            logger.warning(
                "[ZhiHui] Compacted oversized Wan frame title=%r budget=%s",
                str(frame.get("title") or "")[:40],
                budget,
            )
            return candidate
    logger.warning(
        "[ZhiHui] Wan frame still oversized after compact title=%r; will truncate prompt",
        str(frame.get("title") or "")[:40],
    )
    return _compact_frame_fields(frame, budget=40)


def pack_frames_for_wan(
    frames: list[dict[str, Any]],
    *,
    style_seed: str = "",
    batch_role: str = "",
    max_per_batch: int = WAN_MAX_N,
    max_chars: int = WAN_PROMPT_MAX_CHARS,
) -> list[list[dict[str, Any]]]:
    """
    Pack frames into Wan jobs using branch + n + char limits together.

    - Never mix different focus_branch keys in one chunk.
    - n ≤ max_per_batch (Wan 组图).
    - Composed prompt length ≤ max_chars (DashScope 5000).
    """
    size = clamp_wan_n(max_per_batch)
    if not frames:
        return []

    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_branch: str | None = None

    for raw_frame in frames:
        if not isinstance(raw_frame, dict):
            continue
        frame = _fit_single_frame(
            raw_frame,
            style_seed=style_seed,
            batch_role=batch_role,
            max_chars=max_chars,
        )
        branch_key = _focus_branch_key(frame)
        branch_changed = current_branch is not None and branch_key != current_branch
        would_overflow_n = len(current) >= size
        would_overflow_chars = bool(current) and (
            _prompt_len(
                style_seed=style_seed,
                batch_role=batch_role,
                frames=[*current, frame],
            )
            > max_chars
        )
        if current and (branch_changed or would_overflow_n or would_overflow_chars):
            chunks.append(current)
            current = []
            current_branch = None
        current.append(frame)
        current_branch = branch_key

    if current:
        chunks.append(current)
    return chunks


def split_frames_for_wan(
    frames: list[dict[str, Any]],
    *,
    max_per_batch: int = WAN_MAX_N,
    style_seed: str = "",
    batch_role: str = "",
    max_chars: int = WAN_PROMPT_MAX_CHARS,
) -> list[list[dict[str, Any]]]:
    """Chunk frames for Wan: branch boundary + n≤12 + char budget."""
    return pack_frames_for_wan(
        frames,
        style_seed=style_seed,
        batch_role=batch_role,
        max_per_batch=max_per_batch,
        max_chars=max_chars,
    )


def plan_batches_to_wan_jobs(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert planner JSON into Wan job specs.

    Each item: ``{batch_role, style_seed, frames, prompt, n}``.
    Packing applies branch boundary, n≤12, and 5000-char limits together.
    """
    style_seed = str(plan.get("style_seed") or "").strip()
    raw_batches = plan.get("batches")
    jobs: list[dict[str, Any]] = []
    if not isinstance(raw_batches, list) or not raw_batches:
        return jobs

    for batch in raw_batches:
        if not isinstance(batch, dict):
            continue
        frames = batch.get("frames")
        if not isinstance(frames, list):
            continue
        clean_frames = [frame for frame in frames if isinstance(frame, dict)]
        if not clean_frames:
            continue
        role = str(batch.get("batch_role") or "").strip()
        for chunk in pack_frames_for_wan(
            clean_frames,
            style_seed=style_seed,
            batch_role=role,
        ):
            prompt = build_wan_batch_prompt(
                style_seed=style_seed,
                frames=chunk,
                batch_role=role,
            )
            jobs.append(
                {
                    "batch_role": role,
                    "style_seed": style_seed,
                    "frames": chunk,
                    "prompt": prompt,
                    "n": len(chunk),
                }
            )
    return jobs
