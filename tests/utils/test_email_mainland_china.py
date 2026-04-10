"""Tests for mainland China email domain policy."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from utils.email_mainland_china import (
    is_mainland_china_email_domain,
    raise_if_mainland_china_email_for_overseas_registration,
)


@pytest.mark.parametrize(
    ("host", "expected"),
    (
        ("qq.com", True),
        ("user@qq.com".split("@")[1], True),
        ("mail.tsinghua.edu.cn", True),
        ("example.org.cn", True),
        ("mit.edu", False),
        ("student.university.ac.uk", False),
    ),
)
def test_is_mainland_china_email_domain(host: str, expected: bool) -> None:
    assert is_mainland_china_email_domain(host) is expected


def test_raise_blocks_qq() -> None:
    with pytest.raises(HTTPException) as excinfo:
        raise_if_mainland_china_email_for_overseas_registration("a@qq.com", "en")
    assert excinfo.value.status_code == 400


def test_raise_allows_mit() -> None:
    raise_if_mainland_china_email_for_overseas_registration("a@mit.edu", "en")
