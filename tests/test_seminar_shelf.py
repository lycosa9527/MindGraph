"""Shelf destination flags for seminar files and diagrams."""

import pytest

from services.features.mindmate_collab.seminar_shelf import shelf_flags, shelf_title


def test_resource_shelf_is_listed_and_not_an_artifact() -> None:
    """资源 keeps the file in the shared folder."""
    assert shelf_flags("resource") == (True, False)


def test_artifact_shelf_stays_out_of_the_folder() -> None:
    """产物 stays out of the shared folder."""
    assert shelf_flags("artifact") == (False, True)


def test_unknown_shelf_is_rejected() -> None:
    """Only the two shelves are valid."""
    with pytest.raises(ValueError, match="file_type"):
        shelf_flags("chat")


def test_shelf_title_falls_back_and_caps_length() -> None:
    """Empty captions become MindGraph, long ones stay within the filename cap."""
    assert shelf_title("  ") == "MindGraph"
    assert len(shelf_title("图" * 200)) == 180
