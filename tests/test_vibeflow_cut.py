"""Personal-knowledge cut and named-section load."""

from services.knowledge.document_structure import StructureHeading
from services.knowledge.vibeflow_context import personal_context_block
from services.knowledge.vibeflow_cut import build_vibeflow_pieces, toc_is_confirmed


def _body(label: str) -> str:
    return (label + " ") * 40


def _sample_text() -> str:
    return (
        "1 Opening\n"
        + _body("opening")
        + "\n2 Teachers AI Competency Frameworks\n"
        + _body("frameworks")
        + "\n2.1 First child\n"
        + _body("child")
        + "\n2.2 Second child\n"
        + _body("sibling")
        + "\n3 Closing\n"
        + _body("closing")
    )


def _outline() -> list[StructureHeading]:
    return [
        StructureHeading(title="1 Opening", level=1),
        StructureHeading(title="2 Teachers AI Competency Frameworks", level=1),
        StructureHeading(title="2.1 First child", level=2),
        StructureHeading(title="2.2 Second child", level=2),
        StructureHeading(title="3 Closing", level=1),
    ]


def test_confirmed_outline_keeps_each_entry_whole() -> None:
    """A confirmed outline stays one markdown object per heading."""
    text = _sample_text()
    headings = _outline()
    assert toc_is_confirmed(text, headings)
    pieces = build_vibeflow_pieces(text, headings)
    numbers = [piece.section_number for piece in pieces]
    assert numbers == ["1", "2", "2.1", "2.2", "3"]
    assert all(piece.index == 1 for piece in pieces)


def test_bookmark_page_cuts_when_the_title_is_not_in_the_text() -> None:
    """A bookmark page start is the cut when the title is absent from the text."""
    page = "word " * 80
    text = "\n\n".join([page, page, page])
    headings = [
        StructureHeading(title="1 Opening", level=1, page=1),
        StructureHeading(title="2 Parent section", level=1, page=2),
        StructureHeading(title="2.1 Child only in the bookmark", level=2, page=3),
    ]
    starts = [0, len(page) + 2, 2 * (len(page) + 2)]
    page_info = [
        {"page": 1, "start": starts[0], "end": starts[1]},
        {"page": 2, "start": starts[1], "end": starts[2]},
        {"page": 3, "start": starts[2], "end": len(text)},
    ]
    pieces = build_vibeflow_pieces(text, headings, page_info)
    numbers = [piece.section_number for piece in pieces]
    assert numbers == ["1", "2", "2.1"]


def test_outline_keeps_text_before_the_first_bookmark() -> None:
    """Text before the first heading is stored as a document window."""
    cover = "HSBC SICAV Peternelchen B 25 087 "
    text = cover + "\n" + _sample_text()
    pieces = build_vibeflow_pieces(text, _outline())
    assert pieces[0].section_number == "document"
    assert "Peternelchen" in pieces[0].text
    assert "1" in [piece.section_number for piece in pieces]


def test_missing_titles_fall_back_to_windows() -> None:
    """An unconfirmed outline falls back to token windows."""
    text = _body("plain") * 8
    headings = [
        StructureHeading(title="Not in the file", level=1),
        StructureHeading(title="Also missing", level=1),
        StructureHeading(title="Still missing", level=1),
    ]
    assert not toc_is_confirmed(text, headings)
    pieces = build_vibeflow_pieces(text, headings)
    assert pieces
    assert {piece.section_number for piece in pieces} == {"document"}


def test_named_section_includes_children(monkeypatch) -> None:
    """Loading a parent section includes its children and excludes the next parent."""
    entries = [
        {"section_number": "2", "title": "Teachers AI Competency Frameworks", "index": 1, "key": "parent"},
        {"section_number": "2.1", "title": "First child", "index": 1, "key": "child"},
        {"section_number": "2.2", "title": "Second child", "index": 1, "key": "sibling"},
        {"section_number": "3", "title": "Closing", "index": 1, "key": "other"},
    ]
    texts = {
        "parent": "parent body",
        "child": "child body",
        "sibling": "sibling body",
        "other": "other body",
    }
    monkeypatch.setattr("services.knowledge.vibeflow_context.load_package_manifest", lambda _user, _package: entries)
    monkeypatch.setattr("services.knowledge.vibeflow_context.read_object_text", lambda key: texts[key])
    monkeypatch.setattr("services.knowledge.vibeflow_context.vector_section_entries", lambda *_args, **_kwargs: [])

    block = personal_context_block(1, 9, "Teachers AI Competency Frameworks")
    assert "parent body" in block
    assert "child body" in block
    assert "sibling body" in block
    assert "other body" not in block

    child_block = personal_context_block(1, 9, "2.1")
    assert "child body" in child_block
    assert "sibling body" not in child_block
    assert "parent body" not in child_block


def test_short_outline_keeps_a_vector_hit(monkeypatch) -> None:
    """A short outline keeps room for a fused vector section."""
    entries = [
        {"section_number": "2.1", "title": "First child", "index": 1, "key": "child"},
        {"section_number": "annex", "title": "Digital Literacy Framework for Teachers", "index": 1, "key": "china"},
    ]
    texts = {"child": "child body", "china": "china framework"}
    monkeypatch.setattr("services.knowledge.vibeflow_context.load_package_manifest", lambda _user, _package: entries)
    monkeypatch.setattr("services.knowledge.vibeflow_context.read_object_text", lambda key: texts[key])
    monkeypatch.setattr(
        "services.knowledge.vibeflow_context.vector_section_entries",
        lambda *_args, **_kwargs: [entries[1]],
    )

    block = personal_context_block(1, 9, "2.1")
    assert "child body" in block
    assert "china framework" in block


def test_full_outline_does_not_give_its_budget_to_a_vector_hit(monkeypatch) -> None:
    """A full outline is clipped at both ends and does not add a vector section."""
    entries = [
        {"section_number": "2.1", "title": "First child", "index": 1, "key": "child"},
        {"section_number": "annex", "title": "Digital Literacy Framework for Teachers", "index": 1, "key": "china"},
    ]
    texts = {"child": "C" * 13000, "china": "china framework"}
    monkeypatch.setattr("services.knowledge.vibeflow_context.load_package_manifest", lambda _user, _package: entries)
    monkeypatch.setattr("services.knowledge.vibeflow_context.read_object_text", lambda key: texts[key])
    monkeypatch.setattr(
        "services.knowledge.vibeflow_context.vector_section_entries",
        lambda *_args, **_kwargs: [entries[1]],
    )

    block = personal_context_block(1, 9, "2.1")
    assert "china framework" not in block
    assert "[...]" in block


def test_open_label_uses_the_vector_channel(monkeypatch) -> None:
    """An open label uses the fused vector order."""
    entries = [
        {"section_number": "annex", "title": "Digital Literacy Framework for Teachers", "index": 1, "key": "china"},
        {"section_number": "3", "title": "Implementation Scenarios", "index": 1, "key": "scenarios"},
    ]
    texts = {"china": "china framework", "scenarios": "macro meso micro"}
    monkeypatch.setattr("services.knowledge.vibeflow_context.load_package_manifest", lambda _user, _package: entries)
    monkeypatch.setattr("services.knowledge.vibeflow_context.read_object_text", lambda key: texts[key])
    monkeypatch.setattr(
        "services.knowledge.vibeflow_context.vector_section_entries",
        lambda *_args, **_kwargs: [entries[1], entries[0]],
    )

    block = personal_context_block(1, 9, "advice to china")
    assert block.index("macro meso micro") < block.index("china framework")
