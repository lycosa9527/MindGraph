"""Tests for school consultation payload validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from routers.auth.thinking_coins import SchoolConsultationBody


def test_valid_body_passes() -> None:
    """Normal inquiry payload is accepted."""
    body = SchoolConsultationBody(
        name="张三",
        phone="13800000000",
        organization="测试中学",
        note="需要私有化部署",
    )
    assert body.name == "张三"
    assert body.phone == "13800000000"


def test_phone_rejects_letters() -> None:
    """Phone must not contain arbitrary text."""
    with pytest.raises(ValidationError):
        SchoolConsultationBody(
            name="张三",
            phone="not-a-phone",
            organization="测试中学",
        )


def test_name_strips_fake_mention() -> None:
    """User-supplied <@userid> in fields is stripped before WeCom send."""
    body = SchoolConsultationBody(
        name="张三 <@evil>",
        phone="13800000000",
        organization="测试中学",
    )
    assert "<@" not in body.name


def test_note_allows_multiline() -> None:
    """Note may contain short multiline text."""
    body = SchoolConsultationBody(
        name="张三",
        phone="021-12345678",
        organization="测试中学",
        note="第一行\n第二行",
    )
    assert "第一行" in body.note
    assert "第二行" in body.note


def test_landline_phone_accepted() -> None:
    """Landline-style numbers with punctuation are allowed."""
    body = SchoolConsultationBody(
        name="李四",
        phone="(021) 1234-5678",
        organization="测试小学",
    )
    assert body.phone == "(021) 1234-5678"
