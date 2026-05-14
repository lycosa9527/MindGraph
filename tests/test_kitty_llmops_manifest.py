"""Kitty LLMOps manifest shape."""

from __future__ import annotations

from services.kitty_voice.kitty_llmops_manifest import build_kitty_llmops_manifest


def test_kitty_llmops_manifest_keys():
    m = build_kitty_llmops_manifest()
    assert m["version"] == 1
    assert "patch_context" in m["hub_mutation_ops"]
    assert "update_center" in m["diagram_voice_intents"]
    assert len(m["modules"]) >= 3
    assert "mermaid_flow" in m
    assert len(m["special_flows"]) == 3
    assert m["special_flows"][0]["name"] == "paragraph_path"
