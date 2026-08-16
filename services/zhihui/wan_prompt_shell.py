"""Compatibility re-export — Wan prompt shell lives in mind_classroom."""

from services.mind_classroom.wan_prompt_shell import (
    WAN_PROMPT_MAX_CHARS,
    build_wan_batch_prompt,
    plan_batches_to_wan_jobs,
    split_frames_for_wan,
)

__all__ = [
    "WAN_PROMPT_MAX_CHARS",
    "build_wan_batch_prompt",
    "plan_batches_to_wan_jobs",
    "split_frames_for_wan",
]
