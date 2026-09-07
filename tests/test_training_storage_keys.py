"""Training COS folder key contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.cos_env_prefix import cos_app_identity, cos_feature_prefix
from config.settings import config
from services.features.training.courses.constants import DOUBLE_BUBBLE_COURSE_ID
from services.features.training.storage import backend as storage_backend
from services.features.training.storage.backend import delete_course_prefix
from services.features.training.storage.keys import (
    build_object_key,
    course_folder,
    course_id_from_key,
    is_scoped_course_object_key,
    suffix_for_upload,
    training_public_asset_url,
)


def test_suffix_for_upload_falls_back_to_content_type() -> None:
    """Camera/blob files often have no extension; MIME still yields a key suffix."""
    assert suffix_for_upload("slide.PNG", "image/jpeg") == ".png"
    assert suffix_for_upload("blob", "image/png") == ".png"
    with pytest.raises(ValueError, match="suffix"):
        suffix_for_upload("blob", "application/octet-stream")


def test_course_folder_and_cover_key() -> None:
    """Cover objects live at courses/{id}/cover.ext."""
    folder = course_folder(DOUBLE_BUBBLE_COURSE_ID)
    assert folder == f"courses/{DOUBLE_BUBBLE_COURSE_ID}"
    key = build_object_key(DOUBLE_BUBBLE_COURSE_ID, "cover", "unused-id", ".png")
    assert key == f"{folder}/cover.png"
    assert is_scoped_course_object_key(key)
    assert course_id_from_key(key) == DOUBLE_BUBBLE_COURSE_ID
    assert training_public_asset_url(key) == f"/api/training/assets/{key}"


def test_slide_and_video_keys_stay_in_course_folder() -> None:
    """Slides and videos stay under the same course prefix."""
    asset_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    slide = build_object_key(DOUBLE_BUBBLE_COURSE_ID, "slide", asset_id, "jpg")
    video = build_object_key(DOUBLE_BUBBLE_COURSE_ID, "video", asset_id, ".mp4")
    assert slide == f"courses/{DOUBLE_BUBBLE_COURSE_ID}/slides/{asset_id}.jpg"
    assert video == f"courses/{DOUBLE_BUBBLE_COURSE_ID}/videos/{asset_id}.mp4"
    assert is_scoped_course_object_key(slide)
    assert is_scoped_course_object_key(video)


def test_reject_foreign_or_swapped_keys() -> None:
    """Reject invalid ids, roles, and path traversal."""
    asset_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    with pytest.raises(ValueError):
        build_object_key("not-a-uuid", "cover", "x", ".png")
    thumb = build_object_key(DOUBLE_BUBBLE_COURSE_ID, "thumb", asset_id, ".png")
    assert thumb == f"courses/{DOUBLE_BUBBLE_COURSE_ID}/thumbs/{asset_id}.png"
    assert is_scoped_course_object_key(thumb)
    with pytest.raises(ValueError):
        build_object_key(DOUBLE_BUBBLE_COURSE_ID, "avatar", asset_id, ".png")
    assert not is_scoped_course_object_key("showcase/posts/abc/cover.png")
    assert not is_scoped_course_object_key(f"courses/{DOUBLE_BUBBLE_COURSE_ID}/../secret.png")


def test_delete_course_prefix_removes_local_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a course wipes its local media folder."""
    monkeypatch.setattr(storage_backend, "cos_training_enabled", lambda: False)
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "static" / "training" / "courses" / DOUBLE_BUBBLE_COURSE_ID
    folder.mkdir(parents=True)
    (folder / "cover.png").write_bytes(b"png")
    delete_course_prefix(DOUBLE_BUBBLE_COURSE_ID)
    assert not folder.exists()


def test_cos_app_identity_uses_environment_suffix() -> None:
    """Local / test / production already have ENVIRONMENT; reuse that suffix."""
    assert cos_app_identity("production") == "mindgraph"
    assert cos_app_identity("prod") == "mindgraph"
    assert cos_app_identity("test") == "mindgraph-Test"
    assert cos_app_identity("development") == "mindgraph-Dev"
    assert cos_app_identity("dev") == "mindgraph-Dev"


def test_cos_feature_prefix_follows_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Feature prefix is {env}/training unless an override is set."""
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    assert cos_feature_prefix("training") == "test/training"
    assert cos_feature_prefix("training", "training/mindgraph-e2e-smoke") == ("training/mindgraph-e2e-smoke")
    with pytest.raises(ValueError):
        cos_feature_prefix("  ")


def test_training_prefix_follows_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """COS_TRAINING_PREFIX defaults from ENVIRONMENT; override still wins."""
    monkeypatch.delenv("COS_TRAINING_PREFIX", raising=False)
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    config.refresh_env_cache()
    try:
        assert config.COS_TRAINING_PREFIX == "test/training"
        monkeypatch.setenv("ENVIRONMENT", "development")
        config.refresh_env_cache()
        assert config.COS_TRAINING_PREFIX == "dev/training"
        monkeypatch.setenv("COS_TRAINING_PREFIX", "training/mindgraph-e2e-smoke")
        config.refresh_env_cache()
        assert config.COS_TRAINING_PREFIX == "training/mindgraph-e2e-smoke"
    finally:
        config.refresh_env_cache()
