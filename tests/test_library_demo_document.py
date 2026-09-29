"""Library demo documents keep notes and type style, and drop unsafe HTML."""

from services.features.library_demo_document import normalize_library_demo
from services.features.library_demo_thumbnails import png_is_acceptable


def test_keeps_lists_notes_and_type_style() -> None:
    """Named lists keep speaker notes, emphasis, and the chosen type style."""
    document = normalize_library_demo(
        {
            "lists": [
                {
                    "id": "list-1",
                    "name": "Monday class",
                    "diagramIds": ["d1", "d1", ""],
                    "captions": {
                        "d1": {
                            "text": "Compare the two rivers.",
                            "html": "<p><strong>Compare the two rivers.</strong></p>",
                            "fontSize": 22,
                            "fontFace": "serif",
                        }
                    },
                }
            ],
            "lastId": "list-1",
            "captions": {
                "d1": {
                    "text": "Compare the two rivers.",
                    "fontSize": 22,
                    "fontFace": "serif",
                }
            },
        }
    )
    assert document.last_id == "list-1"
    assert document.lists[0].diagram_ids == ["d1"]
    assert document.lists[0].captions["d1"].font_face == "serif"
    assert document.lists[0].captions["d1"].html is not None
    assert document.captions["d1"].font_size == 22
    stored = document.model_dump(by_alias=True, exclude_none=True)
    assert stored["lastId"] == "list-1"
    assert stored["lists"][0]["diagramIds"] == ["d1"]
    assert stored["captions"]["d1"]["fontSize"] == 22


def test_drops_script_html_and_unknown_last_list() -> None:
    """Unsafe note markup is dropped, and a missing list cannot stay selected."""
    document = normalize_library_demo(
        {
            "lists": [{"id": "list-1", "name": "Rivers", "diagramIds": ["d1"], "captions": {}}],
            "lastId": "missing",
            "captions": {
                "d1": {
                    "text": "Safe line",
                    "html": "<script>alert(1)</script><p>Safe line</p>",
                    "fontSize": 18,
                    "fontFace": "sans",
                }
            },
        }
    )
    assert document.last_id is None
    assert document.captions["d1"].text == "Safe line"
    assert document.captions["d1"].html is None


def test_keeps_list_thumbnail_urls_and_drops_foreign_ones() -> None:
    """Only same-origin list thumbnail URLs are stored with the demo document."""
    document = normalize_library_demo(
        {
            "lists": [],
            "thumbnails": {
                "diagram-1": {
                    "url": "/api/auth/library-demo/thumbnails/diagram-1",
                    "updatedAt": "2026-09-30T00:00:00Z",
                },
                "diagram-1-evil": {
                    "url": "https://example.test/thumb.png",
                    "updatedAt": "2026-09-30T00:00:00Z",
                },
            },
        }
    )
    assert document.thumbnails["diagram-1"].url.endswith("/diagram-1")
    assert "diagram-1-evil" not in document.thumbnails


def test_remembers_a_diagram_thumbnail_without_rendering_another() -> None:
    """A revision stamp with no URL means the diagram image is already current."""
    document = normalize_library_demo(
        {
            "lists": [],
            "thumbnails": {"diagram-1": {"updatedAt": "2026-09-30T00:00:00Z"}},
        }
    )
    assert document.thumbnails["diagram-1"].url == ""
    assert document.thumbnails["diagram-1"].updated_at == "2026-09-30T00:00:00Z"


def test_keeps_packed_source_han_face() -> None:
    """Noto Sans SC from the frontend font pack stays on the saved note."""
    document = normalize_library_demo(
        {
            "lists": [],
            "captions": {"d1": {"text": "黑体", "fontSize": 18, "fontFace": "sc"}},
        }
    )
    assert document.captions["d1"].font_face == "sc"
    assert document.captions["d1"].font_color == "ink"


def test_rejects_a_non_object() -> None:
    """A list or other non-object body is not a demo document."""
    try:
        normalize_library_demo(["nope"])
    except ValueError as exc:
        assert "object" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_rejects_a_thumbnail_that_is_not_a_png() -> None:
    """List thumbnails have to be PNG bytes inside the size cap."""
    assert png_is_acceptable(b"\x89PNG\r\n\x1a\n" + b"pixels")
    assert not png_is_acceptable(b"not a png")
    assert not png_is_acceptable(b"")
