"""Tests for Chinese mainland mobile predicate."""
from __future__ import annotations

import pytest

from utils.cn_mobile import is_cn_mainland_mobile


@pytest.mark.parametrize(
    ("phone", "expected"),
    (
        ("13800138000", True),
        ("19912345678", True),
        ("23800138000", False),
        ("1380013800", False),
        ("138001380001", False),
        ("", False),
        (None, False),
        ("abcd138001380", False),
    ),
)
def test_is_cn_mainland_mobile(phone: str | None, expected: bool) -> None:
    assert is_cn_mainland_mobile(phone) is expected
