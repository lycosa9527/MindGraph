"""Expert school bindings are per school and do not consume a home organization."""

from services.auth.expert_school_binding import (
    binding_user_ids_to_add,
    binding_user_ids_to_remove,
    creator_should_auto_bind,
)


def test_adding_a_school_keeps_the_other_bindings() -> None:
    """Selecting an expert for this school does not drop their other schools."""
    current = {1, 2}
    desired = {2, 3}
    assert binding_user_ids_to_add(current, desired) == [3]
    assert binding_user_ids_to_remove(current, desired) == [1]


def test_clearing_this_school_does_not_invent_other_rows() -> None:
    """An empty save removes only the ids currently stored for this school."""
    assert binding_user_ids_to_remove({4, 9}, set()) == [4, 9]
    assert binding_user_ids_to_add(set(), {4}) == [4]


def test_expert_created_orgs_auto_bind() -> None:
    """Only the expert role auto-binds a school they create."""
    assert creator_should_auto_bind("expert")
    assert not creator_should_auto_bind("teacher")
    assert not creator_should_auto_bind("superadmin")
    assert not creator_should_auto_bind(None)
