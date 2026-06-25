"""Tests for cumulative Dify raw dump library merge."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

import main as _main_app

assert _main_app.app.title

from services.dify.export.raw_dump_import import import_zip_file
from services.dify.export.raw_dump_library import (
    find_library_snapshot,
    merge_snapshot_into_library,
)
from services.dify.export.raw_dump_index import DumpIndex, MultiServerDumpStore
from services.dify.export.raw_dump_store import resolve_dump_store

FIXTURE_MINIMAL = Path(__file__).resolve().parent / "fixtures" / "dify_raw_dump" / "dify" / "minimal"
TIMESTAMP_A = "2026-06-26_120000Z"
TIMESTAMP_B = "2026-10-01_080000Z"


def _install_snapshot(tmp_path: Path, timestamp: str, *, conversation_id: str = "c1") -> Path:
    dest = tmp_path / "dify" / timestamp
    shutil.copytree(FIXTURE_MINIMAL, dest)
    manifest = json.loads((FIXTURE_MINIMAL / "manifest.json").read_text(encoding="utf-8"))
    manifest["staging_dir"] = f"/tmp/staging/{timestamp}"
    (dest / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if conversation_id != "c1":
        conv_csv = dest / "conversations.csv"
        conv_csv.write_text(
            conv_csv.read_text(encoding="utf-8").replace("c1", conversation_id),
            encoding="utf-8",
        )
        msg_csv = dest / "messages.csv"
        msg_csv.write_text(
            msg_csv.read_text(encoding="utf-8").replace("c1", conversation_id),
            encoding="utf-8",
        )
    return dest


def test_merge_accumulates_conversations_across_snapshots(tmp_path: Path) -> None:
    """Second snapshot merges new conversations into the library."""
    snap_a = _install_snapshot(tmp_path, TIMESTAMP_A, conversation_id="c1")
    snap_b = _install_snapshot(tmp_path, TIMESTAMP_B, conversation_id="c2")
    merge_snapshot_into_library(tmp_path, snap_a)
    merge_snapshot_into_library(tmp_path, snap_b)

    library = find_library_snapshot(tmp_path, "dify")
    assert library is not None
    assert library.manifest.get("store_kind") == "library"
    merged = library.manifest.get("merged_snapshots")
    assert isinstance(merged, list)
    assert len(merged) == 2

    index = DumpIndex(library)
    convs = index.list_conversations_for_user("mg_user_1", {"app1"})
    assert {item["id"] for item in convs} == {"c1", "c2"}


def test_resolve_dump_store_prefers_library(tmp_path: Path) -> None:
    """Export store reads merged library when present."""
    snap_a = _install_snapshot(tmp_path, TIMESTAMP_A, conversation_id="c1")
    snap_b = _install_snapshot(tmp_path, TIMESTAMP_B, conversation_id="c2")
    merge_snapshot_into_library(tmp_path, snap_a)
    merge_snapshot_into_library(tmp_path, snap_b)

    state = resolve_dump_store(tmp_path)
    snapshot = state.snapshots.get("dify")
    assert snapshot is not None
    assert "library" in str(snapshot.path)
    assert snapshot.manifest.get("store_kind") == "library"

    store = MultiServerDumpStore.load(tmp_path)
    summary = store.data_source_summary()
    assert summary["per_label"]["dify"] == "library"


def test_import_zip_updates_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zip import merges into library automatically."""
    manifest = json.loads((FIXTURE_MINIMAL / "manifest.json").read_text(encoding="utf-8"))
    incoming = tmp_path / "incoming"
    incoming.mkdir(parents=True)
    zip_path = incoming / "dify-dump_dify_test.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for csv_name in FIXTURE_MINIMAL.glob("*.csv"):
            archive.write(csv_name, f"{TIMESTAMP_A}/{csv_name.name}")
        archive.writestr(f"{TIMESTAMP_A}/manifest.json", json.dumps(manifest))

    extracted = import_zip_file(zip_path, tmp_path, move_to_done=False)
    assert extracted.is_dir()
    library = find_library_snapshot(tmp_path, "dify")
    assert library is not None
    index = DumpIndex(library)
    assert len(index.list_conversations_for_user("mg_user_1", {"app1"})) == 1
