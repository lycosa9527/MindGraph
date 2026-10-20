"""Canvas input mode is stored per browser device, including classroom boards."""

from models.domain.canvas_input_device import CANVAS_INPUT_MODES
from utils.db.alembic_migration import load_rls_policy_builder


def test_canvas_input_modes_include_mouse_and_classroom_board():
    """Mouse slash and the classroom board are both stored modes."""
    assert CANVAS_INPUT_MODES == ("mouse", "laptop", "mobile", "board")


def test_canvas_input_device_rls_is_bound_to_the_request_device():
    """A signed-in user can see only the device id set on the transaction."""
    builder = load_rls_policy_builder()
    expr = dict(builder.iter_all_table_policies())["canvas_input_devices"]
    assert "device_id = rls_setting_text('app.canvas_device_id')" in expr
    assert "rls_is_panel_mode()" in expr
    assert "rls_current_user_id() IS NOT NULL" in expr
