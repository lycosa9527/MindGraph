"""Unit tests for DingTalk local DB message text extraction."""

from __future__ import annotations

import json

from file_reader.dingtalk.db_reader import _message_text


def test_message_text_plain() -> None:
    """Plain JSON text payloads decode to the message body."""
    payload = json.dumps({"text": "hello"})
    assert _message_text(1, payload) == "hello"


def test_message_text_skips_system_types() -> None:
    """System and join-card message types yield empty text."""
    join_card = json.dumps(
        {
            "attachments": [
                {
                    "extension": json.dumps(
                        {
                            "text": "邀请你加入钉钉群聊",
                            "title": "邀请你加入群聊",
                        }
                    ),
                    "type": 16,
                }
            ],
            "contentType": 102,
        }
    )
    assert _message_text(102, join_card) == ""
    assert _message_text(104, join_card) == ""
    assert _message_text(1202, json.dumps({"text": "系统提示"})) == ""
