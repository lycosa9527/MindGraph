"""Unit tests for Word add-in production packaging."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from utils.word_addin_packaging import (
    PRODUCTION_ADDIN_ID,
    build_production_manifest_xml,
    build_word_addin_deploy_zip_bytes,
)


def test_production_manifest_rewrites_shell_urls() -> None:
    """Production manifest points shell URLs at the public origin, not localhost."""
    xml = build_production_manifest_xml("https://mg.mindspringedu.com")
    assert "https://mg.mindspringedu.com/word-addin/src/taskpane/mindgraph.html" in xml
    assert "https://mg.mindspringedu.com/word-addin/assets/icons/mindgraph-80.png" in xml
    assert "https://localhost:3000" not in xml
    assert "http://localhost:9527" not in xml
    assert "127.0.0.1" not in xml
    assert "<AppDomain>https://mg.mindspringedu.com</AppDomain>" in xml
    assert "<AppDomain>https://365.kdocs.cn</AppDomain>" in xml
    # Path-suffixed AppDomains are invalid and prevent the CustomTab from showing.
    assert "<AppDomain>https://mg.mindspringedu.com/word-addin</AppDomain>" not in xml
    assert "/word-addin</AppDomain>" not in xml
    # Must not share the git/Vite Dev Id — npm start would overwrite Install.cmd.
    assert f"<Id>{PRODUCTION_ADDIN_ID}</Id>" in xml
    assert "c7b2e9a4-1d3f-4e68-9c05-8f2a6b1d4e70" not in xml
    assert 'DefaultValue="MindGraph"' in xml
    assert "MindGraph Dev" not in xml
    assert 'id="Tab.Label" DefaultValue="MindGraph"' in xml
    assert 'id="Group.Label" DefaultValue="MindGraph"' in xml


def test_deploy_zip_tree_windows_mac_readme() -> None:
    """Deploy zip includes Windows/Mac installers, README, and rewritten manifest."""
    data = build_word_addin_deploy_zip_bytes("https://test.mindspringedu.com")
    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = set(archive.namelist())
        assert names == {
            "README.md",
            "manifest.xml",
            "windows/Install.cmd",
            "windows/Uninstall.cmd",
            "windows/Install-MindGraphWordAddin.ps1",
            "mac/Install.command",
            "mac/Uninstall.command",
            "mac/Install-MindGraphWordAddin.sh",
        }
        mac_info = archive.getinfo("mac/Install.command")
        assert (mac_info.external_attr >> 16) & 0o111
        readme = archive.read("README.md").decode("utf-8")
        assert "Windows 10" in readme
        assert "Windows 11" in readme
        assert "macOS" in readme
        manifest = archive.read("manifest.xml").decode("utf-8")
    assert "https://test.mindspringedu.com/word-addin/" in manifest
    assert "node_modules" not in manifest


def test_normalize_rejects_empty_origin() -> None:
    """Empty public origin is rejected before packaging."""
    with pytest.raises(ValueError):
        build_production_manifest_xml("")
