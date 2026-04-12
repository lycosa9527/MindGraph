"""
Public API: recent entries from project CHANGELOG.md (Keep a Changelog format).
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.utils.changelog_recent import extract_recent_changelog_entries

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHANGELOG_PATH = _PROJECT_ROOT / "CHANGELOG.md"

router = APIRouter(prefix="/changelog", tags=["Changelog"])


class ChangelogEntryResponse(BaseModel):
    """Single release section."""

    title: str = Field(..., description="Heading text after '## ', e.g. '[1.0.0] - 2026-01-01'")
    body: str = Field(..., description="Markdown body for that release (subsections and list items)")


class ChangelogRecentResponse(BaseModel):
    """Recent changelog entries."""

    entries: list[ChangelogEntryResponse]


@router.get("/recent", response_model=ChangelogRecentResponse)
async def get_recent_changelog(
    limit: int = Query(5, ge=1, le=20, description="Number of latest versions to return"),
) -> ChangelogRecentResponse:
    """Return the newest `limit` version sections from CHANGELOG.md."""
    if not CHANGELOG_PATH.is_file():
        raise HTTPException(status_code=503, detail="Changelog file is not available")

    try:
        raw = CHANGELOG_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Could not read changelog") from exc

    parsed = extract_recent_changelog_entries(raw, limit)
    entries = [ChangelogEntryResponse(title=e["title"], body=e["body"]) for e in parsed]
    return ChangelogRecentResponse(entries=entries)
