"""Tests for the MindMate export view model + serializers."""

from __future__ import annotations

import json

from services.dify.export.transcript import (
    ExportBundle,
    ExportConversation,
    conversation_created_at,
    render_html,
    split_message_to_bubbles,
)


def test_split_message_yields_user_then_assistant() -> None:
    """A Dify message with query + answer becomes two ordered bubbles."""
    message = {
        "id": "m1",
        "created_at": 1700000000,
        "query": "hello",
        "answer": "hi there",
        "feedback": {"rating": "like"},
    }
    bubbles = split_message_to_bubbles(message, server=1)
    assert [b.role for b in bubbles] == ["user", "assistant"]
    assert bubbles[0].text == "hello"
    assert bubbles[1].text == "hi there"
    assert bubbles[1].feedback == "like"
    assert all(b.created_at == 1700000000 for b in bubbles)


def test_split_message_skips_empty_sides() -> None:
    """Blank query/answer sides are not emitted as bubbles."""
    assert split_message_to_bubbles({"id": "m", "answer": "only answer"}, 1)[0].role == "assistant"
    assert len(split_message_to_bubbles({"id": "m", "query": "only query"}, 1)) == 1
    assert not split_message_to_bubbles({"id": "m"}, 1)


def test_user_bubble_keeps_message_files() -> None:
    """Uploaded files are preserved on the user bubble."""
    message = {"id": "m", "query": "", "message_files": [{"filename": "a.png"}]}
    bubbles = split_message_to_bubbles(message, 1)
    assert bubbles[0].role == "user"
    assert bubbles[0].files == [{"filename": "a.png"}]


def test_conversation_created_at_fallbacks() -> None:
    """created_at falls back to updated_at then 0, never raising."""
    assert conversation_created_at({"created_at": 5}) == 5
    assert conversation_created_at({"updated_at": 9}) == 9
    assert conversation_created_at({"created_at": "bad"}) == 0
    assert conversation_created_at({}) == 0


def _bundle() -> ExportBundle:
    conv = ExportConversation(
        conversation_id="c1",
        name="Greeting",
        server=2,
        organization_id=42,
        dify_user="mg_user_7",
        user_id=7,
        user_label="Alice",
        channel="web",
        created_at=1700000000,
        updated_at=1700000100,
        bubbles=split_message_to_bubbles(
            {"id": "m1", "created_at": 1700000000, "query": "hi", "answer": "<b>hello</b>"},
            2,
        ),
    )
    return ExportBundle(
        organization_id=42,
        organization_name="Test School",
        scope="single-user",
        conversations=[conv],
    )


def test_bundle_json_is_source_of_truth() -> None:
    """JSON serialization carries full fidelity including the source server."""
    payload = json.loads(_bundle().to_json())
    assert payload["organization_id"] == 42
    assert payload["conversation_count"] == 1
    conv = payload["conversations"][0]
    assert conv["server"] == 2
    assert conv["bubbles"][0]["role"] == "user"
    assert conv["bubbles"][1]["text"] == "<b>hello</b>"


def test_render_html_is_self_contained_and_escaped() -> None:
    """HTML embeds CSS, has no external network refs, and escapes message text."""
    page = render_html(_bundle())
    assert page.startswith("<!DOCTYPE html>")
    assert "<style>" in page
    assert "http://" not in page and "https://" not in page
    assert "&lt;b&gt;hello&lt;/b&gt;" in page  # answer text escaped, not rendered
    assert "Server 2" in page


def test_render_html_shows_dingtalk_chat_scope_badge() -> None:
    """MindBot group scope renders a labeled badge in the HTML transcript."""
    conv = ExportConversation(
        conversation_id="c1",
        name="Group chat",
        server=1,
        organization_id=42,
        dify_user="mindbot_5_staff",
        user_id=7,
        user_label="Alice · DingTalk",
        channel="mindbot",
        created_at=1700000000,
        updated_at=1700000100,
        dingtalk_chat_scope="cross_org_group",
        bubbles=[],
    )
    page = render_html(
        ExportBundle(
            organization_id=42,
            organization_name="Test School",
            scope="whole-org",
            conversations=[conv],
        )
    )
    assert "Cross-org group" in page
    assert "scope-cross-org" in page


def test_render_html_empty_bundle() -> None:
    """An empty bundle still renders a valid page with an empty notice."""
    page = render_html(
        ExportBundle(organization_id=1, organization_name="Empty", scope="whole-org")
    )
    assert "No conversations" in page
