"""Learning Space instruction images stay out of Postgres and prefer COS."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from config.cos_env_prefix import cos_feature_prefix
from config.settings import config
from models.domain.learning_space import LearningAssignment
from routers.features.learning_space.schemas import AssignmentCreate
from services.learning_space.assignments import assignment_public_dict
from services.learning_space.image_storage import (
    IMAGE_REF_PREFIX,
    assert_safe_logical_key,
    build_logical_key,
    decode_data_url,
    delete_stored_images_sync,
    detect_image_content_type,
    persist_instruction_images_sync,
    public_instruction_images,
    put_image_bytes_sync,
    stored_image_keys,
)

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_logical_key_has_no_cos_host() -> None:
    """Persisted keys are relative paths, not durable COS URLs."""
    key = build_logical_key(owner_id=9, filename="notes.PNG")
    assert key.startswith("9/")
    assert key.endswith(".png")
    assert "://" not in key
    assert ".." not in key


def test_safe_logical_key_rejects_traversal() -> None:
    """Relative keys cannot escape the Learning Space prefix."""
    with pytest.raises(ValueError, match="Invalid image key"):
        assert_safe_logical_key("../secret.txt")
    with pytest.raises(ValueError, match="Invalid image key"):
        assert_safe_logical_key("")


def test_public_src_is_access_checked_proxy() -> None:
    """API responses expose a stable download hop, not a presigned COS URL."""
    refs = [f"{IMAGE_REF_PREFIX}7/2026/09/abc.jpg", "https://example.test/a.png"]
    out = public_instruction_images(refs, assignment_id=42)
    assert out[0] == "/api/learning-space/instruction-images/42/0"
    assert out[1] == "https://example.test/a.png"


def test_assignment_public_dict_resolves_refs() -> None:
    """Assignment JSON never embeds stored COS keys as img src."""
    assignment = LearningAssignment(
        class_id=1,
        title="t",
        instructions="",
        template_diagram_id="d1",
        created_by=1,
        organization_id=3,
        instruction_images=[f"{IMAGE_REF_PREFIX}1/2026/09/aa.jpg"],
    )
    assignment.id = 88
    payload = assignment_public_dict(assignment)
    assert payload["instruction_images"] == ["/api/learning-space/instruction-images/88/0"]


def test_schema_rejects_oversized_http_ref() -> None:
    """Short COS refs pass; huge non-data strings do not."""
    AssignmentCreate.model_validate(
        {
            "class_id": 1,
            "title": "t",
            "template_diagram_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "instruction_images": [f"{IMAGE_REF_PREFIX}1/2026/09/aa.jpg"],
        }
    )
    with pytest.raises(ValidationError):
        AssignmentCreate.model_validate(
            {
                "class_id": 1,
                "title": "t",
                "template_diagram_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "instruction_images": ["https://example.test/" + ("a" * 2001)],
            }
        )


def test_detect_image_magic_bytes() -> None:
    """Only real image payloads are accepted for COS/local put."""
    assert detect_image_content_type(_PNG_1X1) == "image/png"
    assert detect_image_content_type(b"<html>not an image</html>") is None
    assert detect_image_content_type(b"\xff\xd8\xff\xe0" + b"\x00" * 12) == "image/jpeg"


def test_put_rejects_html_disguised_as_jpeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Magic-byte check blocks HTML uploaded with an image Content-Type."""
    monkeypatch.setattr(
        "services.learning_space.image_storage.cos_learning_space_enabled",
        lambda: False,
    )
    monkeypatch.setattr("services.learning_space.image_storage.local_root", lambda: tmp_path)
    with pytest.raises(ValueError, match="Unsupported image type"):
        put_image_bytes_sync("4/2026/09/aa.jpg", b"<html>hi</html>", "image/jpeg")


def test_decode_png_data_url() -> None:
    """Legacy data URLs still decode so create can hoist them to COS."""
    decoded = decode_data_url(_PNG_DATA_URL)
    assert decoded is not None
    payload, mime = decoded
    assert mime == "image/png"
    assert payload.startswith(b"\x89PNG")


def test_persist_data_url_uses_cos(monkeypatch: pytest.MonkeyPatch) -> None:
    """New data-URL attachments become lsimg refs via COS put."""
    uploaded: dict[str, bytes] = {}

    def _put(data: bytes, object_key: str, **_kwargs: object) -> bool:
        uploaded[object_key] = data
        return True

    monkeypatch.setattr(
        "services.learning_space.image_storage.cos_learning_space_enabled",
        lambda: True,
    )
    monkeypatch.setattr("services.learning_space.image_storage.upload_bytes", _put)
    stored = persist_instruction_images_sync([_PNG_DATA_URL], owner_id=4)
    assert len(stored) == 1
    assert stored[0].startswith(IMAGE_REF_PREFIX)
    assert uploaded
    assert stored_image_keys(stored)[0] in next(iter(uploaded))


def test_persist_keeps_existing_ref() -> None:
    """Already-uploaded refs are not re-encoded."""
    ref = f"{IMAGE_REF_PREFIX}4/2026/09/deadbeefabcd.jpg"
    stored = persist_instruction_images_sync([ref], owner_id=4)
    assert stored == [ref]


def test_local_put_and_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When COS is off, bytes land under static/learning_space and can be removed."""
    monkeypatch.setattr(
        "services.learning_space.image_storage.cos_learning_space_enabled",
        lambda: False,
    )
    monkeypatch.setattr("services.learning_space.image_storage.local_root", lambda: tmp_path)
    ref = put_image_bytes_sync("4/2026/09/aa.jpg", _PNG_1X1, "image/jpeg")
    assert ref == f"{IMAGE_REF_PREFIX}4/2026/09/aa.jpg"
    assert (tmp_path / "4/2026/09/aa.jpg").is_file()
    delete_stored_images_sync(stored_image_keys([ref]))
    assert not (tmp_path / "4/2026/09/aa.jpg").exists()


def test_learning_space_prefix_follows_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset COS_LEARNING_SPACE_PREFIX follows ENVIRONMENT like workshop."""
    monkeypatch.delenv("COS_LEARNING_SPACE_PREFIX", raising=False)
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    assert cos_feature_prefix("learning-space", "") == "test/learning-space"
    config.refresh_env_cache()
    try:
        monkeypatch.setenv("ENVIRONMENT", "test")
        config.refresh_env_cache()
        assert config.COS_LEARNING_SPACE_PREFIX == "test/learning-space"
        monkeypatch.setenv("COS_LEARNING_SPACE_PREFIX", "learning-space/mindgraph-e2e")
        config.refresh_env_cache()
        assert config.COS_LEARNING_SPACE_PREFIX == "learning-space/mindgraph-e2e"
    finally:
        config.refresh_env_cache()


def test_cos_put_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed COS put does not fall back to stuffing bytes into Postgres."""
    monkeypatch.setattr(
        "services.learning_space.image_storage.cos_learning_space_enabled",
        lambda: True,
    )
    monkeypatch.setattr("services.learning_space.image_storage.upload_bytes", lambda *_a, **_k: False)
    with pytest.raises(ValueError, match="COS"):
        put_image_bytes_sync("4/2026/09/aa.jpg", _PNG_1X1, "image/jpeg")
