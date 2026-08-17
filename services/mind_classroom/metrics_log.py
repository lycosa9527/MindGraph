"""Autocomplete-style timing lines for 思维讲堂 scripts and slide decks."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("services.mind_classroom")


def usage_token_pair(usage: Optional[dict[str, Any]]) -> tuple[Optional[int], Optional[int]]:
    """Prompt / completion counts from an LLM usage dict."""
    if not isinstance(usage, dict):
        return None, None
    tokens_in = _as_int(usage.get("prompt_tokens") or usage.get("input_tokens"))
    tokens_out = _as_int(usage.get("completion_tokens") or usage.get("output_tokens"))
    return tokens_in, tokens_out


def format_token_rate(tokens_out: Optional[int], elapsed: float) -> str:
    """`` (12.3 tok/s)`` when output tokens and elapsed are usable."""
    if tokens_out is None or elapsed <= 0:
        return ""
    return f" ({tokens_out / elapsed:.1f} tok/s)"


def format_token_fields(tokens_in: Optional[int], tokens_out: Optional[int]) -> str:
    """``tokens_in=1 tokens_out=2`` fragment, or empty."""
    parts: list[str] = []
    if tokens_in is not None:
        parts.append(f"tokens_in={tokens_in}")
    if tokens_out is not None:
        parts.append(f"tokens_out={tokens_out}")
    return " ".join(parts)


def format_script_llm_line(
    *,
    elapsed: float,
    usage: Optional[dict[str, Any]] = None,
    chunk_index: Optional[int] = None,
    chunk_total: Optional[int] = None,
    repair: bool = False,
) -> str:
    """One Script LLM completion line (same shape as auto-complete tok/s logs)."""
    tokens_in, tokens_out = usage_token_pair(usage)
    label = "Script LLM"
    if chunk_index is not None and chunk_total is not None:
        label = f"Script LLM chunk {chunk_index}/{chunk_total}"
    if repair:
        label = f"{label} repair"
    token_part = format_token_fields(tokens_in, tokens_out)
    extra = f" {token_part}" if token_part else ""
    return f"[MindClassroom] {label} completed in {elapsed:.2f}s{extra}{format_token_rate(tokens_out, elapsed)}"


def format_job_completed_line(
    *,
    kind: str,
    elapsed: float,
    breakdown: dict[str, float],
    target: str = "",
    extra: str = "",
) -> str:
    """Workflow total + phase breakdown, matching auto-complete."""
    phases = ", ".join(f"{name}={value:.2f}s" for name, value in breakdown.items())
    target_part = f" for {target}" if target else ""
    extra_part = f", {extra}" if extra else ""
    return f"[MindClassroom] {kind} completed in {elapsed:.2f}s{target_part} (breakdown: {phases}){extra_part}"


def format_phase_completed_line(
    *,
    phase: str,
    elapsed: float,
    extra: str = "",
    usage: Optional[dict[str, Any]] = None,
) -> str:
    """Single-phase line: lesson plan, Wan batch, persist."""
    token_part = ""
    rate = ""
    if usage is not None:
        tokens_in, tokens_out = usage_token_pair(usage)
        fields = format_token_fields(tokens_in, tokens_out)
        if fields:
            token_part = f" {fields}"
        rate = format_token_rate(tokens_out, elapsed)
    extra_part = f" {extra}" if extra else ""
    return f"[MindClassroom] {phase} completed in {elapsed:.2f}s{token_part}{rate}{extra_part}"


def log_script_llm_done(
    *,
    elapsed: float,
    usage: Optional[dict[str, Any]] = None,
    chunk_index: Optional[int] = None,
    chunk_total: Optional[int] = None,
    repair: bool = False,
) -> None:
    """INFO: one script LLM call finished."""
    logger.info(
        format_script_llm_line(
            elapsed=elapsed,
            usage=usage,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            repair=repair,
        )
    )


def log_job_completed(
    *,
    kind: str,
    elapsed: float,
    breakdown: dict[str, float],
    target: str = "",
    extra: str = "",
) -> None:
    """INFO: job wall time with phase breakdown."""
    logger.info(
        format_job_completed_line(
            kind=kind,
            elapsed=elapsed,
            breakdown=breakdown,
            target=target,
            extra=extra,
        )
    )


def log_phase_completed(
    *,
    phase: str,
    elapsed: float,
    extra: str = "",
    usage: Optional[dict[str, Any]] = None,
) -> None:
    """INFO: one pipeline phase finished."""
    logger.info(
        format_phase_completed_line(
            phase=phase,
            elapsed=elapsed,
            extra=extra,
            usage=usage,
        )
    )


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
