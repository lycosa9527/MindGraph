"""Tests for Dify raw dump CSV index."""

from __future__ import annotations

from pathlib import Path

import main as _main_app

assert _main_app.app.title

from services.dify.export.raw_dump_index import DumpIndex, MultiServerDumpStore
from services.dify.export.raw_dump_manifest import snapshot_from_dir

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "dify_raw_dump" / "dify" / "minimal"


def test_dump_index_maps_token_to_app_id() -> None:
    snapshot = snapshot_from_dir(FIXTURE_ROOT)
    index = DumpIndex(snapshot)
    assert index.token_to_app_id()["tok1"] == "app1"


def test_dump_index_lists_conversations_for_user() -> None:
    snapshot = snapshot_from_dir(FIXTURE_ROOT)
    index = DumpIndex(snapshot)
    convs = index.list_conversations_for_user("mg_user_1", {"app1"})
    assert len(convs) == 1
    assert convs[0]["id"] == "c1"


def test_dump_index_fetches_messages_with_files_and_feedback() -> None:
    snapshot = snapshot_from_dir(FIXTURE_ROOT)
    index = DumpIndex(snapshot)
    messages = index.fetch_messages_for_conversation("c1")
    assert len(messages) == 1
    message = messages[0]
    assert message["query"] == "hi there"
    assert message["answer"] == "hello back"
    assert message["feedback"]["rating"] == "like"
    assert message["message_files"][0]["url"] == "https://example.com/a.png"


def test_multi_server_store_loads_fixture_when_pointed() -> None:
    base = FIXTURE_ROOT.parent.parent
    store = MultiServerDumpStore.load(base)
    index = store.index_for_slot(1)
    assert index is not None
    assert index.label == "dify"
