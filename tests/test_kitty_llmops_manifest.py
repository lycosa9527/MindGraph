"""Kitty LLMOps manifest shape."""

from __future__ import annotations

from pathlib import Path

from services.kitty.http.llmops_manifest import (
    build_kitty_llmops_manifest,
    kitty_llmops_manifest_paths,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_kitty_llmops_manifest_keys():
    m = build_kitty_llmops_manifest()
    assert m["version"] == 1
    assert "patch_context" in m["hub_mutation_ops"]
    assert "update_center" in m["diagram_voice_intents"]
    assert len(m["modules"]) >= 3
    assert "mermaid_flow" in m
    assert len(m["special_flows"]) == 3
    assert m["special_flows"][0]["name"] == "paragraph_path"


def test_kitty_llmops_manifest_paths_exist_on_disk():
    missing = []
    for rel in kitty_llmops_manifest_paths():
        if rel.endswith("/"):
            if not (_REPO_ROOT / rel.rstrip("/")).is_dir():
                missing.append(rel)
            continue
        if not (_REPO_ROOT / rel).is_file():
            missing.append(rel)
    assert not missing, f"manifest paths missing: {missing}"
