"""Classroom manifesto uses owner RLS, not ZhiHui panel mode."""

from __future__ import annotations

from pathlib import Path


def test_alembic_0103_owner_rls_not_panel_mode() -> None:
    """Classroom tables are owner-scoped, not ZhiHui panel/superadmin RLS."""
    text = Path("alembic/versions/rev_0103_mind_classroom_jobs.py").read_text(encoding="utf-8")
    assert "rls_is_panel_mode" not in text
    assert "user_id = rls_current_user_id()" in text
    assert "rls_is_system_mode()" in text


def test_script_task_is_short_and_slides_are_long() -> None:
    """Canvas-tour jobs stay shorter than Wan decks; each_node needs minutes."""
    text = Path("tasks/mind_classroom_tasks.py").read_text(encoding="utf-8")
    assert "_SCRIPT_SOFT = 600" in text
    assert "_SCRIPT_HARD = 660" in text
    assert "_SLIDE_SOFT = 2400" in text
    assert 'name="mind_classroom.run_script"' in text
    assert 'name="mind_classroom.run_slides"' in text
