"""Real topics must not be treated as blank insert labels."""

import re
from pathlib import Path

from utils.placeholder import is_placeholder_text

_CANVAS_ROOT = Path(__file__).resolve().parents[1] / "frontend/src/locales/messages"
_INSERT_LABEL_KEYS = (
    "braceMap.defaultSubpartFirst",
    "braceMap.defaultSubpartSecond",
    "canvas.toolbar.newAssociation",
    "canvas.toolbar.newAttribute",
    "canvas.toolbar.newBranch",
    "canvas.toolbar.newCause",
    "canvas.toolbar.newChild",
    "canvas.toolbar.newEffect",
    "canvas.toolbar.newItemA",
    "canvas.toolbar.newItemB",
    "canvas.toolbar.newPart",
    "canvas.toolbar.newStep",
    "canvas.toolbar.newSubpart",
    "canvas.toolbar.newSubstep",
    "diagram.newAttribute",
    "diagram.newBranch",
    "diagram.newBridgeLeft",
    "diagram.newBridgeRight",
    "diagram.newCategory",
    "diagram.newCause",
    "diagram.newChild",
    "diagram.newConcept",
    "diagram.newContext",
    "diagram.newEffect",
    "diagram.newItem",
    "diagram.newLeftDifference",
    "diagram.newPart",
    "diagram.newRightDifference",
    "diagram.newSimilarity",
    "diagram.newStep",
    "diagram.newSubitem",
    "diagram.newSubpart",
    "diagram.newSubstep",
)


def test_topics_that_start_with_new_are_kept() -> None:
    """新加坡 and New Zealand are topics on every diagram, not blank nodes."""
    assert is_placeholder_text("新加坡") is False
    assert is_placeholder_text("中国") is False
    assert is_placeholder_text("新疆") is False
    assert is_placeholder_text("New Zealand") is False
    assert is_placeholder_text("New York") is False


def _canvas_label(locale: str, key: str) -> str:
    text = (_CANVAS_ROOT / locale / "canvas.ts").read_text(encoding="utf-8")
    match = re.search(rf"'{re.escape(key)}':\s*'((?:\\'|[^'])*)'", text)
    assert match is not None, f"{locale} {key}"
    return match.group(1).replace("\\'", "'")


def test_zh_and_en_insert_labels_stay_placeholders() -> None:
    """The server list matches the labels the canvas actually writes in zh, zh-tw, and en."""
    for locale in ("zh", "zh-tw", "en"):
        for key in _INSERT_LABEL_KEYS:
            assert is_placeholder_text(_canvas_label(locale, key)) is True


def test_unedited_insert_labels_stay_placeholders() -> None:
    """Labels written when a node is added are still empty."""
    assert is_placeholder_text("新步骤") is True
    assert is_placeholder_text("新子部分 1") is True
    assert is_placeholder_text("新节点") is True
    assert is_placeholder_text("New Step") is True
    assert is_placeholder_text("new step") is True
    assert is_placeholder_text("Topic A") is True
    assert is_placeholder_text("主题A") is True
    assert is_placeholder_text("Similarity 1") is True
