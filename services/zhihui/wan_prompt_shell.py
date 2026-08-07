"""Merge lesson-plan frames into Wan 组图 prompts (prompt set B)."""

from __future__ import annotations

from typing import Any

from services.t2i.wan_image_client import WAN_MAX_N, clamp_wan_n
from services.zhihui.prompts.wan_image_shell import WAN_IMAGE_SHELL


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


def build_wan_batch_prompt(
    *,
    style_seed: str,
    frames: list[dict[str, Any]],
    batch_role: str = "",
) -> str:
    """Compose one Wan 组图 text from shell + style + frames."""
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
    text = "\n".join(lines).strip()
    return text[:5000]


def split_frames_for_wan(
    frames: list[dict[str, Any]],
    *,
    max_per_batch: int = WAN_MAX_N,
) -> list[list[dict[str, Any]]]:
    """Chunk frames so each Wan call stays within n≤12."""
    size = clamp_wan_n(max_per_batch)
    if not frames:
        return []
    return [frames[i : i + size] for i in range(0, len(frames), size)]


def plan_batches_to_wan_jobs(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert planner JSON into Wan job specs.

    Each item: ``{batch_role, style_seed, frames, prompt, n}``.
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
        for chunk in split_frames_for_wan(clean_frames):
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
