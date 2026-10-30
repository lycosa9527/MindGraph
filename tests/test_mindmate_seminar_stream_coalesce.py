"""MindMate seminar answer pieces are painted in short batches, not per token."""

from __future__ import annotations

from typing import Callable, Optional

from services.features.mindmate_seminar.stream_coalesce import SeminarStreamCoalescer


def _clock(now: list[float]) -> Callable[[], float]:
    def read() -> float:
        return now[0]

    return read


def _coalescer(
    now: list[float],
    *,
    interval_seconds: float = 0.08,
    max_held_chars: int = 400,
) -> SeminarStreamCoalescer:
    return SeminarStreamCoalescer(
        interval_seconds=interval_seconds,
        max_held_chars=max_held_chars,
        clock=_clock(now),
    )


def test_first_piece_paints_immediately() -> None:
    """The bubble appears on the first upstream piece, with nothing held back."""
    now = [0.0]
    coalescer = _coalescer(now)
    assert coalescer.push("你") == "你"
    assert coalescer.flush() is None


def test_burst_inside_the_interval_becomes_one_delta() -> None:
    """Pieces that arrive before the next paint leave together."""
    now = [0.0]
    coalescer = _coalescer(now)
    assert coalescer.push("A") == "A"
    now[0] = 0.01
    assert coalescer.push("B") is None
    now[0] = 0.02
    assert coalescer.push("C") is None
    assert coalescer.flush() == "BC"
    assert coalescer.flush() is None


def test_gap_longer_than_the_interval_paints_twice() -> None:
    """A piece that arrives after the interval is its own paint."""
    now = [0.0]
    coalescer = _coalescer(now)
    assert coalescer.push("A") == "A"
    now[0] = 0.1
    assert coalescer.push("B") == "B"


def test_held_text_paints_when_the_character_cap_is_reached() -> None:
    """A large piece is not held for the full interval."""
    now = [0.0]
    coalescer = _coalescer(now, max_held_chars=4)
    assert coalescer.push("A") == "A"
    now[0] = 0.01
    assert coalescer.push("bb") is None
    now[0] = 0.02
    assert coalescer.push("cd") == "bbcd"


def test_joined_deltas_equal_the_original_text() -> None:
    """Every character is painted once, in order."""
    now = [0.0]
    coalescer = _coalescer(now)
    pieces = ["你", "好", "，", "世", "界"]
    times = [0.0, 0.01, 0.02, 0.09, 0.1]
    emitted: list[str] = []
    for piece, stamp in zip(pieces, times, strict=True):
        now[0] = stamp
        delta: Optional[str] = coalescer.push(piece)
        if delta:
            emitted.append(delta)
    tail = coalescer.flush()
    if tail:
        emitted.append(tail)
    assert emitted == ["你", "好，世", "界"]
    assert "".join(emitted) == "".join(pieces)


def test_zero_interval_paints_every_piece() -> None:
    """A flush interval of 0 keeps one frame per upstream piece."""
    coalescer = SeminarStreamCoalescer(interval_seconds=0, max_held_chars=400)
    assert coalescer.push("A") == "A"
    assert coalescer.push("BB") == "BB"
    assert coalescer.push("") is None
    assert coalescer.flush() is None
