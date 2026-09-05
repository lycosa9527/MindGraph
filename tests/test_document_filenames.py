"""Tests for space-unique knowledge document file names."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from services.knowledge.document_filenames import (
    FILE_NAME_MAX_LEN,
    allocate_unique_file_name,
    insert_unique_named_row,
    next_unique_file_name,
)


def test_next_unique_file_name_keeps_unused_name() -> None:
    """A free name is returned unchanged."""
    assert next_unique_file_name("Pasted note.md", set()) == "Pasted note.md"


def test_next_unique_file_name_suffixes_collision() -> None:
    """The first taken name becomes stem_1.ext."""
    taken = {"Pasted note.md"}
    assert next_unique_file_name("Pasted note.md", taken) == "Pasted note_1.md"


def test_next_unique_file_name_skips_taken_suffixes() -> None:
    """Already-used suffixes are skipped."""
    taken = {"Pasted note.md", "Pasted note_1.md", "Pasted note_2.md"}
    assert next_unique_file_name("Pasted note.md", taken) == "Pasted note_3.md"


def test_next_unique_file_name_exhausted() -> None:
    """Give up after the suffix cap instead of looping forever."""
    with patch("services.knowledge.document_filenames._MAX_SUFFIX", 1):
        with pytest.raises(ValueError, match="Could not allocate"):
            next_unique_file_name("a.md", {"a.md", "a_1.md"})


@pytest.mark.asyncio
async def test_allocate_unique_file_name_reads_space_names() -> None:
    """Allocation queries existing names in the target space."""
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=["Pasted note.md"])))
        )
    )
    name = await allocate_unique_file_name(db, 19, "Pasted note.md")
    assert name == "Pasted note_1.md"


def test_next_unique_file_name_clips_to_column_limit() -> None:
    """Suffixed names stay within the VARCHAR(255) column."""
    original = f"{'n' * 252}.md"
    assert len(original) == FILE_NAME_MAX_LEN
    result = next_unique_file_name(original, {original})
    assert result.endswith("_1.md")
    assert len(result) <= FILE_NAME_MAX_LEN


@pytest.mark.asyncio
async def test_insert_unique_named_row_retries_integrity_error() -> None:
    """A raced INSERT retries with the failed name treated as taken."""
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=["note.md"]))))
    )
    db.commit = AsyncMock(side_effect=[IntegrityError("dup", {}, Exception("dup")), None])
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    built: list[str] = []

    def _build(name: str) -> SimpleNamespace:
        built.append(name)
        return SimpleNamespace(file_name=name)

    row = await insert_unique_named_row(db, 19, "note.md", _build)
    assert built == ["note_1.md", "note_2.md"]
    assert row.file_name == "note_2.md"
    db.rollback.assert_awaited_once()
    assert db.commit.await_count == 2
