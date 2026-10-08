"""Live school lists for a bound expert follow the current binding rows."""

from services.auth.expert_live_scope import (
    bound_org_label,
    parse_bound_org_label,
    session_registry_org_ids,
)
from services.features.mindmate_collab.redis_keys import registry_keys_for_visibility


def test_registry_keeps_host_and_adds_bound_schools() -> None:
    """A home school stays first. Extra bindings are listed after it."""
    assert session_registry_org_ids(4, [9, 4, 2]) == [4, 9, 2]


def test_registry_uses_bindings_when_the_expert_has_no_home_school() -> None:
    """No home school means only the schools in the binding table."""
    assert session_registry_org_ids(None, [3, 3, 8]) == [3, 8]
    assert not session_registry_org_ids(None, [])


def test_bound_label_omits_the_host_school() -> None:
    """Redis stores the extra schools, not a second copy of the host."""
    assert bound_org_label(4, [4, 9]) == "9"
    assert parse_bound_org_label("9, x, 9, 2") == [9, 2]


def test_org_room_with_bindings_skips_the_global_registry() -> None:
    """An expert room is listed on bound schools, not every school."""
    keys = list(registry_keys_for_visibility(None, "organization", [3, 8]))
    assert len(keys) == 2
    assert all("global" not in key for key in keys)
    assert list(registry_keys_for_visibility(None, "organization", []))[0].endswith("global")
