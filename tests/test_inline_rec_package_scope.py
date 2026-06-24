"""Tests for package-scoped RAG wiring in inline recommendations.

Covers the cheap, deterministic pieces that gate package-scoped retrieval for
the inline recommendations endpoint:

* ``_build_rag_query`` — derives a retrieval query from topic + edited node + stage.
* ``resolve_package_context_block`` — short-circuits (no DB, no LLM) when inputs
  are missing or when the File Center feature flag is disabled.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from routers.inline_recommendations import _build_rag_query
from services.knowledge import package_rag_context
from services.knowledge.package_rag_context import resolve_package_context_block


def _req(nodes, node_id, stage):
    """Build a minimal request-like object for the query builder."""
    return SimpleNamespace(nodes=nodes, node_id=node_id, stage=stage)


def test_build_rag_query_combines_topic_current_and_stage():
    """Query joins the topic node, the edited node text, and the stage."""
    nodes = [
        {"id": "topic", "text": "Photosynthesis"},
        {"id": "branch-l-1-0", "text": "Light reactions"},
    ]
    query = _build_rag_query(_req(nodes, "branch-l-1-0", "children"))
    assert "Photosynthesis" in query
    assert "Light reactions" in query
    assert "children" in query


def test_build_rag_query_falls_back_to_first_node_for_topic():
    """When no explicit topic/root node exists, the first node is the topic."""
    nodes = [{"id": "n0", "text": "Roots"}, {"id": "n1", "text": "Leaves"}]
    query = _build_rag_query(_req(nodes, "n1", "branches"))
    assert "Roots" in query
    assert "Leaves" in query


def test_build_rag_query_handles_empty_nodes():
    """No nodes still yields a (possibly empty) string, never raises."""
    assert _build_rag_query(_req([], None, "")) == ""


@pytest.mark.asyncio
async def test_resolve_package_context_inactive_without_inputs():
    """Missing user/diagram/query returns an inactive result with no DB access."""
    result = await resolve_package_context_block(None, "diagram-1", "query", "en")
    assert result.package_active is False
    assert result.context_block == ""

    result = await resolve_package_context_block(1, None, "query", "en")
    assert result.package_active is False

    result = await resolve_package_context_block(1, "diagram-1", "", "en")
    assert result.package_active is False


@pytest.mark.asyncio
async def test_resolve_package_context_inactive_when_feature_disabled(monkeypatch):
    """When File Center is gated off, resolution short-circuits before any DB call."""
    monkeypatch.setattr(
        type(package_rag_context.config),
        "FEATURE_KNOWLEDGE_SPACE",
        property(lambda _self: False),
    )
    result = await resolve_package_context_block(1, "diagram-1", "topic stage", "en")
    assert result.package_active is False
    assert result.context_block == ""
