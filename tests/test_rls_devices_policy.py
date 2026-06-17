"""Devices table RLS policy uses student_id (not user_id)."""

from utils.db.alembic_migration import load_rls_policy_builder

DEVICE_EXPR = load_rls_policy_builder().DEVICE_EXPR


def test_device_policy_expr_uses_student_id():
    """Test device policy expr uses student id."""
    assert "student_id" in DEVICE_EXPR
    assert "rls_diagram_visible(student_id)" in DEVICE_EXPR
    assert "rls_diagram_visible(user_id)" not in DEVICE_EXPR
