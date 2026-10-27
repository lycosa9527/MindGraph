"""Client shell is stored per browser device so a tablet can lock mobile or desktop."""

from pathlib import Path

from models.domain.client_shell_device import CLIENT_SHELLS
from utils.db.alembic_migration import load_rls_policy_builder

_ROOT = Path(__file__).resolve().parents[1]


def test_client_shells_are_mobile_or_desktop():
    """The account control only offers the two shells."""
    assert CLIENT_SHELLS == ("mobile", "desktop")


def test_client_shell_device_rls_is_bound_to_the_request_device():
    """A signed-in user can see only the device id set on the transaction."""
    builder = load_rls_policy_builder()
    expr = dict(builder.iter_all_table_policies())["client_shell_devices"]
    assert "device_id = rls_setting_text('app.client_shell_device_id')" in expr
    assert "rls_is_panel_mode()" in expr
    assert "rls_current_user_id() IS NOT NULL" in expr


def test_client_shell_column_allows_only_mobile_or_desktop():
    """A stored shell cannot be a value the account control does not offer."""
    expected = "shell IN (" + ", ".join(f"'{name}'" for name in CLIENT_SHELLS) + ")"
    model = (_ROOT / "models/domain/client_shell_device.py").read_text(encoding="utf-8")
    migration_path = _ROOT / "alembic/versions/rev_0158_client_shell_devices.py"
    migration = migration_path.read_text(encoding="utf-8")
    assert expected in model
    assert expected in migration
    assert "ck_client_shell_devices_shell" in model
    assert "ck_client_shell_devices_shell" in migration
