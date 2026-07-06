"""MindMate collab join resume token claim matching."""

from __future__ import annotations

import pytest

from services.features.mindmate_collab.resume_tokens import (
    join_resume_claims_match_user_room,
    peek_join_resume_claims_async,
)


def test_resume_claims_match_user_and_code() -> None:
    """Accept resume token when user, code, and session id all match."""
    claims = {"u": 5, "c": "ABC-DEF", "s": "sess-1"}
    assert join_resume_claims_match_user_room(5, "abc-def", claims, "sess-1") is True


def test_resume_claims_reject_wrong_session_id() -> None:
    """Reject resume token when session id does not match the live room."""
    claims = {"u": 5, "c": "ABC-DEF", "s": "sess-old"}
    assert join_resume_claims_match_user_room(5, "ABC-DEF", claims, "sess-new") is False


def test_resume_claims_allow_missing_session_check() -> None:
    """Allow resume when caller omits session id verification."""
    claims = {"u": 5, "c": "ABC-DEF", "s": "sess-1"}
    assert join_resume_claims_match_user_room(5, "ABC-DEF", claims) is True


@pytest.mark.asyncio
async def test_peek_rejects_overlong_resume_token() -> None:
    """Resume tokens longer than 96 characters are ignored."""
    assert await peek_join_resume_claims_async("a" * 97) is None
