"""Desktop pet versions compare as numbers, and a bad manifest block is ignored."""

from __future__ import annotations

from services.features.desktop_pet.update_manifest import is_newer, platform_release, version_tuple


def test_version_tuple_ignores_a_text_suffix() -> None:
    """0.1.0 is older than 0.2.0, and a letter suffix does not change the number."""
    assert version_tuple("0.1.0") < version_tuple("0.2.0")
    assert version_tuple("1.0.0a") == (1, 0, 0)
    assert is_newer("0.1.10", "0.1.9") is True
    assert is_newer("0.1.0", "0.1.0") is False


def test_platform_release_requires_key_and_hash() -> None:
    """A Windows publish must not look like a Mac download."""
    manifest = {
        "version": "0.2.0",
        "windows": {"key": "dev/desktop-pet/0.2.0/MindGraphPet-windows.zip", "sha256": "abc", "size": 4},
    }
    assert platform_release(manifest, "mac") is None
    windows = platform_release(manifest, "windows")
    assert windows is not None
    assert windows["sha256"] == "abc"
