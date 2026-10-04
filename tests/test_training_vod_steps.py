"""Course steps keep online-library and required-tutorial fields."""

from __future__ import annotations

import pytest

from services.features.training.courses.repository import _step_payload
from services.features.training.courses.serialize import snapshot_step_payload
from services.features.vod.catalog import VodCatalogError, folder_list_clause
from services.features.vod.folders import normalize_folder_name

MEDIA_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def test_step_payload_keeps_vod_and_mandatory() -> None:
    """Autosave must not drop the library pick or the required-tutorial flag."""
    payload = _step_payload(
        {
            "type": "page",
            "vod_media_id": MEDIA_ID,
            "vod_autoplay": True,
            "mandatory": True,
        }
    )
    assert payload["vod_media_id"] == MEDIA_ID
    assert payload["vod_autoplay"] is True
    assert payload["mandatory"] is True


def test_step_payload_drops_blank_vod_and_rejects_junk() -> None:
    """A cleared picker stores null; a bad id is rejected."""
    assert _step_payload({"type": "page"})["vod_media_id"] is None
    assert _step_payload({"type": "page"})["mandatory"] is False
    with pytest.raises(ValueError, match="vod_media_id"):
        _step_payload({"type": "page", "vod_media_id": "not-a-uuid"})


def test_step_payload_keeps_ui_lock() -> None:
    """A locked open list must survive save and be rejected when unknown."""
    payload = _step_payload({"type": "page", "page_key": "mindgraph", "ui_lock": "mindgraph-language"})
    assert payload["ui_lock"] == "mindgraph-language"
    assert snapshot_step_payload(payload)["ui_lock"] == "mindgraph-language"
    with pytest.raises(ValueError, match="ui_lock"):
        _step_payload({"type": "page", "ui_lock": "not-a-panel"})
    assert _step_payload({"type": "page", "page_key": "canvas", "ui_lock": "mindgraph-language"})["ui_lock"] is None


def test_step_payload_keeps_always_play() -> None:
    """Demo mode must survive save so the course plays on every visit."""
    payload = _step_payload({"type": "page", "always_play": True})
    assert payload["always_play"] is True
    assert snapshot_step_payload(payload)["always_play"] is True
    assert _step_payload({"type": "page"})["always_play"] is False


def test_step_payload_keeps_voice_and_music() -> None:
    """Voice and music asset ids stay on the slide payload."""
    voice = "6f2a1c90-db01-4000-8000-00000000db11"
    music = "6f2a1c90-db01-4000-8000-00000000db12"
    payload = _step_payload({"type": "page", "voice_asset_id": voice, "music_asset_id": music})
    assert payload["voice_asset_id"] == voice
    assert payload["music_asset_id"] == music
    assert _step_payload({"type": "page"})["voice_asset_id"] is None
    with pytest.raises(ValueError, match="voice_asset_id"):
        _step_payload({"type": "page", "voice_asset_id": "nope"})


def test_step_payload_keeps_mascot_asset_and_drops_playback_url() -> None:
    """A custom mascot stores its asset id. The playback URL is filled on read."""
    asset_id = "6f2a1c90-db01-4000-8000-00000000db13"
    payload = _step_payload(
        {
            "type": "page",
            "overlays": [
                {
                    "kind": "role",
                    "asset_id": asset_id,
                    "src": "/api/training/assets/stale.webp",
                    "x": 88,
                }
            ],
        }
    )
    assert payload["overlays"] == [{"kind": "role", "asset_id": asset_id, "x": 88}]
    with pytest.raises(ValueError, match="asset_id"):
        _step_payload({"type": "page", "overlays": [{"kind": "role", "asset_id": "nope"}]})


def test_step_payload_keeps_user_dropdown_lock() -> None:
    """The avatar menu can stay locked on a canvas slide."""
    payload = _step_payload({"type": "page", "page_key": "canvas", "ui_lock": "user-dropdown"})
    assert payload["ui_lock"] == "user-dropdown"


def test_step_payload_keeps_vod_window_size() -> None:
    """A resized video window must survive save and reject a tiny box."""
    payload = _step_payload({"type": "page", "vod_width": 48, "vod_height": 30})
    assert payload["vod_width"] == 48
    assert payload["vod_height"] == 30
    assert snapshot_step_payload(payload)["vod_width"] == 48
    assert _step_payload({"type": "page"})["vod_width"] is None
    with pytest.raises(ValueError, match="vod_width"):
        _step_payload({"type": "page", "vod_width": 5})


def test_snapshot_carries_vod_fields_to_followers() -> None:
    """Live lessons read the Redis snapshot, so the player fields must be on it."""
    step = snapshot_step_payload(
        {
            "type": "page",
            "vod_media_id": MEDIA_ID,
            "vod_autoplay": True,
            "mandatory": True,
        }
    )
    assert step["vod_media_id"] == MEDIA_ID
    assert step["vod_autoplay"] is True
    assert step["mandatory"] is True


def test_folder_name_and_list_clause() -> None:
    """Folder names collapse whitespace; the list filter accepts unfiled and uuids."""
    assert normalize_folder_name("  intro   clips  ") == "intro clips"
    with pytest.raises(VodCatalogError):
        normalize_folder_name("   ")
    assert folder_list_clause("") is None
    assert folder_list_clause("none") is not None
    assert folder_list_clause(MEDIA_ID) is not None
    with pytest.raises(VodCatalogError):
        folder_list_clause("not-a-folder")
