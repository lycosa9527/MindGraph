"""Autocomplete-style 思维讲堂 script / slide-deck timing lines."""

from __future__ import annotations

import pytest

from services.mind_classroom.metrics_log import (
    format_job_completed_line,
    format_phase_completed_line,
    format_script_llm_line,
    log_job_completed,
    log_phase_completed,
    log_script_llm_done,
    usage_token_pair,
)


def test_usage_token_pair_reads_prompt_and_completion() -> None:
    """DashScope-style usage keys map to in/out counts."""
    tokens_in, tokens_out = usage_token_pair({"prompt_tokens": 2023, "completion_tokens": 4457})
    assert tokens_in == 2023
    assert tokens_out == 4457


def test_script_llm_line_matches_autocomplete_tok_s() -> None:
    """Script LLM line includes elapsed, tokens, and tok/s."""
    line = format_script_llm_line(
        elapsed=76.45,
        usage={"prompt_tokens": 2023, "completion_tokens": 4457},
    )
    assert line.startswith("[MindClassroom] Script LLM completed in 76.45s")
    assert "tokens_in=2023" in line
    assert "tokens_out=4457" in line
    assert "(58.3 tok/s)" in line


def test_script_llm_chunk_and_repair_labels() -> None:
    """each_node chunks and JSON repair stay visible in the same metric line."""
    chunk = format_script_llm_line(
        elapsed=20.0,
        usage={"input_tokens": 100, "output_tokens": 200},
        chunk_index=2,
        chunk_total=4,
    )
    assert "Script LLM chunk 2/4 completed in 20.00s" in chunk
    repair = format_script_llm_line(
        elapsed=12.0,
        usage={"prompt_tokens": 10, "completion_tokens": 20},
        repair=True,
    )
    assert "Script LLM repair completed in 12.00s" in repair


def test_job_completed_line_has_breakdown() -> None:
    """Job total matches auto-complete workflow breakdown logs."""
    line = format_job_completed_line(
        kind="Script generation",
        elapsed=76.50,
        breakdown={"llm": 76.45, "persist": 0.05},
        target="canvas_tour",
        extra="steps=8 job=abc",
    )
    assert line == (
        "[MindClassroom] Script generation completed in 76.50s for canvas_tour "
        "(breakdown: llm=76.45s, persist=0.05s), steps=8 job=abc"
    )


def test_phase_completed_line_for_lesson_plan() -> None:
    """Lesson-plan phase includes tokens when usage is present."""
    line = format_phase_completed_line(
        phase="Lesson plan",
        elapsed=40.12,
        extra="job=abc",
        usage={"prompt_tokens": 800, "completion_tokens": 1200},
    )
    assert line.startswith("[MindClassroom] Lesson plan completed in 40.12s")
    assert "tokens_in=800" in line
    assert "tokens_out=1200" in line
    assert "job=abc" in line


def test_metric_helpers_write_info(caplog: pytest.LogCaptureFixture) -> None:
    """INFO logger name is services.mind_classroom so uvicorn shows it."""
    with caplog.at_level("INFO", logger="services.mind_classroom"):
        log_script_llm_done(elapsed=1.5, usage={"prompt_tokens": 10, "completion_tokens": 30})
        log_phase_completed(phase="Wan batch 1/2", elapsed=2.0, extra="urls=3")
        log_job_completed(
            kind="Slide deck",
            elapsed=10.0,
            breakdown={"plan": 4.0, "wan": 5.5, "persist": 0.5},
            target="slide_deck",
            extra="slides=3/3 job=j1",
        )
    messages = [rec.message for rec in caplog.records]
    assert any("Script LLM completed in 1.50s" in msg for msg in messages)
    assert any("Wan batch 1/2 completed in 2.00s" in msg for msg in messages)
    assert any("Slide deck completed in 10.00s for slide_deck" in msg for msg in messages)
