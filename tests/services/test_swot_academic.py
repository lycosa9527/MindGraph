"""Tests for combined Kikobeats + pyswot academic policy."""
from __future__ import annotations

import pytest

from services.auth import swot_academic


@pytest.mark.parametrize(
    ("email", "expected"),
    (
        ("user@gmail.com", False),
        ("user@ox.ac.uk", True),
        ("user@mail.harvard.edu", True),
    ),
)
def test_passes_combined_academic_policy(email: str, expected: bool) -> None:
    assert swot_academic.passes_combined_academic_policy(email) is expected


def test_kikobeats_suffix_matches_parent_domain() -> None:
    assert swot_academic.passes_combined_academic_policy("u@mail.google.com") is False


def test_is_academic_email_matches_combined_predicate() -> None:
    assert swot_academic.is_academic_email("u@ox.ac.uk") is True
    assert swot_academic.is_academic_email("u@gmail.com") is False
