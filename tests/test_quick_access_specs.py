"""Built-in quick-access diagrams and saved-spec cleaning."""

from services.utils.quick_access_prompts import QUICK_ACCESS_PROMPT_KEYS
from services.utils.quick_access_specs import (
    QUICK_ACCESS_SPEC_DIAGRAM_TYPES,
    clean_quick_access_saved_specs,
    default_quick_access_specs,
)


def test_default_quick_access_specs_cover_every_prompt() -> None:
    """Each inspiration preset has a diagram the canvas can open."""
    specs = default_quick_access_specs()
    assert set(specs) == set(QUICK_ACCESS_PROMPT_KEYS)
    for entry in specs.values():
        assert entry["diagramType"] in QUICK_ACCESS_SPEC_DIAGRAM_TYPES
        assert isinstance(entry["spec"], dict)
        assert entry["spec"]


def test_clean_quick_access_saved_specs_drops_incomplete_entries() -> None:
    """Only a known prompt with text and a diagram is kept."""
    cleaned = clean_quick_access_saved_specs(
        {
            "landing.international.example1": {
                "text": "  自定义光合作用  ",
                "diagramType": "mindmap",
                "spec": {"topic": "光合作用"},
            },
            "landing.international.example2": {
                "text": "",
                "diagramType": "tree_map",
                "spec": {"topic": "空"},
            },
            "not-a-prompt": {
                "text": "忽略",
                "diagramType": "mindmap",
                "spec": {"topic": "忽略"},
            },
        }
    )
    assert list(cleaned) == ["landing.international.example1"]
    assert cleaned["landing.international.example1"]["text"] == "自定义光合作用"
