"""Tests for workshop list ETag helpers."""

from services.features.workshop_chat.workshop_list_etag import etag_is_not_modified


def test_etag_is_not_modified_same_weak_etag():
    etag = 'W/"a1b2c3d4e5f678901234567890abcdef"'
    assert etag_is_not_modified(etag, etag) is True


def test_etag_is_not_modified_weak_vs_strong_form():
    inner = '"a1b2c3d4e5f678901234567890abcdef"'
    weak = f"W/{inner}"
    assert etag_is_not_modified(inner, weak) is True
    assert etag_is_not_modified(weak, inner) is True


def test_etag_is_not_modified_multiple_candidates():
    want = 'W/"target"'
    header = 'W/"other", W/"target"'
    assert etag_is_not_modified(header, want) is True


def test_etag_is_not_modified_wildcard():
    assert etag_is_not_modified("*", 'W/"anything"') is True


def test_etag_is_not_modified_mismatch():
    assert etag_is_not_modified('W/"a"', 'W/"b"') is False


def test_etag_is_not_modified_empty_header():
    assert etag_is_not_modified(None, 'W/"x"') is False
    assert etag_is_not_modified("", 'W/"x"') is False
