"""Tests for DingTalk inbound prompt extraction."""

from __future__ import annotations

from services.mindbot.platforms.dingtalk.inbound import extract_inbound_prompt


def test_group_text_strips_leading_at_mentions() -> None:
    body = {
        "msgtype": "text",
        "text": {"content": "@MyBot\u200b hello world"},
        "conversationType": "2",
    }
    prompt, mt = extract_inbound_prompt(body)
    assert mt == "text"
    assert "@MyBot" not in prompt
    assert "hello world" in prompt


def test_private_text_keeps_at_mentions() -> None:
    body = {
        "msgtype": "text",
        "text": {"content": "@MyBot hello"},
        "conversationType": "1",
    }
    prompt, mt = extract_inbound_prompt(body)
    assert mt == "text"
    assert "@MyBot" in prompt


def test_group_conversation_type_string() -> None:
    body = {
        "msgtype": "text",
        "text": {"content": "@A @B ping"},
        "conversation_type": "group",
    }
    prompt, _mt = extract_inbound_prompt(body)
    assert "@" not in prompt.split()[0]
    assert "ping" in prompt


def test_picture_msgtype() -> None:
    body = {
        "msgtype": "picture",
        "content": {"pictureDownloadCode": "abc123"},
    }
    prompt, mt = extract_inbound_prompt(body)
    assert mt == "picture"
    assert "pictureDownloadCode=abc123" in prompt


def test_file_msgtype() -> None:
    body = {
        "msgtype": "file",
        "file": {"fileName": "a.pdf", "downloadCode": "d1"},
    }
    prompt, mt = extract_inbound_prompt(body)
    assert mt == "file"
    assert "a.pdf" in prompt
