"""Resume helpers for classroom slide generation."""

from __future__ import annotations

from typing import Any


def next_slide_index(slides: list[Any]) -> int:
    """First missing slide_index in 0..max, else max+1."""
    indexes = sorted({int(slide.slide_index) for slide in slides if getattr(slide, "slide_index", None) is not None})
    if not indexes:
        return len(slides)
    expected = 0
    for index in indexes:
        if index < 0:
            continue
        if index > expected:
            return expected
        if index == expected:
            expected += 1
    return expected


def iter_batch_resume_ranges(
    batch_frame_counts: list[int],
    resume_slide: int,
) -> list[tuple[int, int, int, int]]:
    """Absolute slide ranges and skip offsets for each Wan batch."""
    ranges: list[tuple[int, int, int, int]] = []
    frames_done = 0
    resume = max(0, int(resume_slide))
    for count in batch_frame_counts:
        frame_count = max(0, int(count))
        batch_start = frames_done
        batch_end = frames_done + frame_count
        if resume >= batch_end:
            skip_in_batch = frame_count
        else:
            skip_in_batch = max(0, resume - batch_start)
        ranges.append((batch_start, batch_end, skip_in_batch, frame_count))
        frames_done = batch_end
    return ranges
