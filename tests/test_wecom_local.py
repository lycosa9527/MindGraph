"""Tests for WeCom local detection helpers."""

from __future__ import annotations

from file_reader.wecom.local import WeComLocalStatus, detect_wecom_local


def test_detect_wecom_local_returns_status() -> None:
    status = detect_wecom_local()
    assert isinstance(status, WeComLocalStatus)
    assert isinstance(status.process_running, bool)
    assert isinstance(status.encrypted_db_count, int)
