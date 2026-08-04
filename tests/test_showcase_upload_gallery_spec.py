"""Gallery upload complete must persist nested JSONB path mutations."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from models.domain.showcase import ShowcasePost
from routers.features.showcase.helpers import heal_gallery_image_paths
from services.showcase.uploads.pipeline import apply_key_to_post
from services.showcase.uploads.roles import resolve_upload_role


def test_apply_key_to_post_gallery_deep_copies_nested_entries() -> None:
    """Shallow copy + in-place path write must not mutate the original entry."""
    original_entry = {"kind": "image", "pending": True, "filename": "a.png"}
    post = cast(
        ShowcasePost,
        SimpleNamespace(
            case_type="diagram_case",
            thumbnail_path=None,
            spec={"type": "diagram_case", "gallery": [original_entry]},
        ),
    )
    role = resolve_upload_role("gallery_0")
    with patch("services.showcase.uploads.pipeline.flag_modified") as flag_modified:
        previous = apply_key_to_post(
            post,
            role_spec=role,
            logical_key="showcase/posts/post-1/gallery_0.png",
            filename="a.png",
        )
    assert not previous
    assert "path" not in original_entry
    assert original_entry.get("pending") is True
    spec = post.spec
    assert isinstance(spec, dict)
    gallery = spec["gallery"]
    assert isinstance(gallery, list)
    assert gallery[0] is not original_entry
    assert gallery[0]["path"] == "showcase/posts/post-1/gallery_0.png"
    assert "pending" not in gallery[0]
    flag_modified.assert_called_once_with(post, "spec")


def test_heal_gallery_image_paths_fills_missing_path_from_storage() -> None:
    """Approve heal recovers path when the object already exists in storage."""
    spec = {
        "type": "diagram_case",
        "gallery": [{"kind": "image", "pending": True, "filename": "shot.png"}],
    }
    key = "showcase/posts/post-1/gallery_0.png"
    with patch(
        "routers.features.showcase.helpers.resolve_gallery_image_storage_path",
        return_value=key,
    ):
        changed = heal_gallery_image_paths("post-1", spec)
    assert changed is True
    assert spec["gallery"][0]["path"] == key
    assert "pending" not in spec["gallery"][0]
    assert spec["source"] == "gallery"


def test_heal_gallery_image_paths_noop_when_still_missing() -> None:
    """Heal leaves pending slots untouched when storage has no object."""
    spec = {
        "type": "diagram_case",
        "gallery": [{"kind": "image", "pending": True}],
    }
    with patch(
        "routers.features.showcase.helpers.resolve_gallery_image_storage_path",
        return_value=None,
    ):
        changed = heal_gallery_image_paths("post-1", spec)
    assert changed is False
    assert "path" not in spec["gallery"][0]
