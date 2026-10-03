"""Bilingual spec mirror checks. The primary object stays valid when the mirror is dropped."""

import pytest

from agents.concept_maps.concept_map_agent import ConceptMapAgent
from agents.diagram_bilingual.split import mirror_matches, peel_bilingual_spec, transplant_secondary
from utils.bilingual_prompt import bilingual_max_tokens, bilingual_prompt_scope


def test_mirror_matches_parallel_lists() -> None:
    """Parallel string lists count as the same shape."""
    primary = {"topic": "光合作用", "context": ["叶绿体", "阳光"]}
    secondary = {"topic": "Photosynthesis", "context": ["Chloroplast", "Sunlight"]}
    assert mirror_matches(primary, secondary) is True


def test_peel_drops_short_secondary_and_keeps_primary() -> None:
    """A short mirror is removed and the primary lists stay."""
    spec = {
        "topic": "光合作用",
        "context": ["叶绿体", "阳光"],
        "secondary": {"topic": "Photosynthesis", "context": ["Chloroplast"]},
    }
    assert peel_bilingual_spec(spec, "zh", "en") is False
    assert "secondary" not in spec
    assert spec["context"] == ["叶绿体", "阳光"]


def test_peel_keeps_matching_mirror_and_records_languages() -> None:
    """A matching mirror stays and records the language pair."""
    spec = {
        "topic": "光合作用",
        "children": [{"text": "光", "children": []}],
        "secondary": {
            "topic": "Photosynthesis",
            "children": [{"text": "Light", "children": []}],
        },
    }
    assert peel_bilingual_spec(spec, "zh", "en") is True
    assert spec["languages"] == {"primary": "zh", "secondary": "en"}
    assert spec["secondary"]["children"][0]["text"] == "Light"


def test_transplant_trims_extra_items_and_copies_agent_ids() -> None:
    """Extra mirror items are trimmed and agent ids are copied onto it."""
    raw = {
        "topic": "光合作用",
        "children": [{"text": "光"}],
        "secondary": {
            "topic": "Photosynthesis",
            "children": [{"text": "Light"}, {"text": "Water"}],
        },
    }
    built = {
        "topic": "光合作用",
        "children": [{"id": "light", "text": "光"}],
    }
    transplant_secondary(raw, built)
    assert built["secondary"]["topic"] == "Photosynthesis"
    assert built["secondary"]["children"] == [{"id": "light", "text": "Light"}]
    assert mirror_matches(built, built["secondary"]) is True


@pytest.mark.asyncio
async def test_concept_map_enhance_keeps_secondary_mirror() -> None:
    """Rebuilding a concept map must not throw away the second language."""
    agent = ConceptMapAgent(model="qwen")
    spec = {
        "topic": "光合作用",
        "concepts": ["叶绿体", "阳光"],
        "relationships": [{"from": "光合作用", "to": "叶绿体", "label": "发生在"}],
        "secondary": {
            "topic": "Photosynthesis",
            "concepts": ["Chloroplast", "Sunlight"],
            "relationships": [{"from": "Photosynthesis", "to": "Chloroplast", "label": "occurs in"}],
        },
    }
    result = await agent.enhance_spec(spec)
    assert result["success"] is True
    enhanced = result["spec"]
    assert enhanced["secondary"]["topic"] == "Photosynthesis"
    assert enhanced["secondary"]["concepts"] == ["Chloroplast", "Sunlight"]
    assert peel_bilingual_spec(enhanced, "zh", "en") is True


def test_bilingual_max_tokens_stays_put_for_a_single_language() -> None:
    """A single-language call keeps its token cap. A bilingual call raises it."""
    assert bilingual_max_tokens(1000) == 1000
    with bilingual_prompt_scope("en"):
        assert bilingual_max_tokens(1000) == 8192
        assert bilingual_max_tokens(4000) == 8192
