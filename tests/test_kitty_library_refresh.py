"""Tests for Kitty library refresh gating (voice edit clobber prevention)."""

from __future__ import annotations

import time

import pytest

from services.kitty.context.library_refresh import (
    bump_voice_mutation_freshness,
    should_skip_library_refresh,
)
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions


def test_bump_voice_mutation_freshness_marks_session() -> None:
    vid = create_voice_session(user_id="1", diagram_session_id="lib-1", diagram_type="circle_map")
    try:
        bump_voice_mutation_freshness(vid)
        sess = voice_sessions[vid]
        assert float(sess.get("_last_voice_mutation_mono") or 0.0) > 0.0
        assert float(sess.get("_last_context_update_mono") or 0.0) > 0.0
        assert should_skip_library_refresh(vid) is True
    finally:
        voice_sessions.pop(vid, None)


def test_should_skip_library_refresh_after_context_update() -> None:
    vid = create_voice_session(user_id="1", diagram_session_id="lib-2", diagram_type="circle_map")
    try:
        voice_sessions[vid]["_last_context_update_mono"] = time.monotonic()
        assert should_skip_library_refresh(vid) is True
    finally:
        voice_sessions.pop(vid, None)


def test_should_not_skip_when_stale_and_force() -> None:
    vid = create_voice_session(user_id="1", diagram_session_id="lib-3", diagram_type="circle_map")
    try:
        voice_sessions[vid]["_last_context_update_mono"] = time.monotonic() - 60.0
        assert should_skip_library_refresh(vid) is False
        assert should_skip_library_refresh(vid, force=True) is False
    finally:
        voice_sessions.pop(vid, None)
