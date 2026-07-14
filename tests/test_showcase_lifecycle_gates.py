"""Showcase lifecycle: review gates and media-ready checks."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from routers.features.showcase.helpers import (
    assert_post_ready_for_approval,
    post_media_ready_for_approval,
)


def test_teaching_design_requires_attachment_before_approval() -> None:
    """Approve must reject teaching designs without an attachment path."""
    with pytest.raises(HTTPException) as exc:
        assert_post_ready_for_approval(case_type="teaching_design", spec={"type": "teaching_design"})
    assert exc.value.status_code == 400
    assert post_media_ready_for_approval(case_type="teaching_design", spec={"type": "teaching_design"}) is False

    assert (
        post_media_ready_for_approval(
            case_type="teaching_design",
            spec={"type": "teaching_design", "attachment_path": "showcase/posts/x/attachment.pdf"},
        )
        is True
    )


def test_pending_gallery_blocks_approval() -> None:
    """Approve must reject unresolved gallery image slots."""
    spec = {
        "type": "diagram_case",
        "gallery": [{"kind": "image", "pending": True}],
    }
    with pytest.raises(HTTPException) as exc:
        assert_post_ready_for_approval(case_type="diagram_case", spec=spec)
    assert exc.value.status_code == 400

    ready = {
        "type": "diagram_case",
        "gallery": [{"kind": "image", "path": "showcase/posts/x/gallery_0.png"}],
    }
    assert post_media_ready_for_approval(case_type="diagram_case", spec=ready) is True


def test_diagram_template_without_gallery_is_ready() -> None:
    """Canvas/template specs without gallery do not need media uploads."""
    assert post_media_ready_for_approval(case_type="diagram_template", spec={"type": "mind_map"}) is True
