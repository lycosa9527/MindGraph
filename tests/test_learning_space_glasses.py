"""Glasses sheet URL contract and OCR parse."""

from fastapi.routing import APIRoute

from routers.features.learning_space.glasses import router
from services.learning_space.glasses_bind import wearer_qr_payload
from services.learning_space.glasses_contract import (
    BIND_DISPLAY,
    CAPTURES_PATH,
    GLASSES_POC_ORIGIN,
    INGEST_PATH,
    REMOTE_PATH,
    SHEETS_PATH,
    capture_image_path,
    glasses_ingest_url,
    parse_sheet_payload,
    sheet_id_from_payload,
    sheet_payload,
)
from services.learning_space.glasses_events import glasses_events_channel
from services.learning_space.glasses_vision import (
    SHEET_OCR_MODEL,
    parse_learning_sheet_read,
    printed_diagram_outline,
)


def test_glasses_poc_posts_to_the_test_server() -> None:
    """The glasses client has one absolute URL, and it is the test host."""
    assert GLASSES_POC_ORIGIN == "https://test.mindspringedu.com"
    assert glasses_ingest_url() == "https://test.mindspringedu.com/api/learning-space/glasses/ingest"
    assert INGEST_PATH == "/api/learning-space/glasses/ingest"
    assert REMOTE_PATH == "/api/learning-space/glasses/remote"
    assert SHEETS_PATH == "/api/learning-space/glasses/sheets"
    assert CAPTURES_PATH == "/api/learning-space/glasses/captures"


def test_sheet_payload_round_trip() -> None:
    """The shared QR text is the sheet UUID. A class page adds its sequence."""
    sheet_id = "11111111-2222-3333-4444-555555555555"
    assert sheet_payload(sheet_id) == f"mg://sheet/{sheet_id}"
    assert sheet_id_from_payload(sheet_payload(sheet_id)) == sheet_id
    assert sheet_id_from_payload("https://example.com") == ""
    assert sheet_payload(sheet_id, 7) == f"mg://sheet/{sheet_id}/7"
    assert parse_sheet_payload(sheet_payload(sheet_id, 7)) == (sheet_id, 7)
    assert parse_sheet_payload(f"{sheet_id}/7") == (sheet_id, 7)
    assert parse_sheet_payload(f"mg://sheet/{sheet_id}/0") == ("", 0)


def test_wearer_qr_uses_the_sheet_prefix_the_glasses_already_read() -> None:
    """Settings QR must be a code the current glasses build photographs."""
    token_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert wearer_qr_payload(token_id) == f"mg://sheet/{token_id}"
    assert BIND_DISPLAY == "智能设备已绑定"


def test_capture_image_path() -> None:
    """Teachers load the original photo on the same host as the page."""
    assert capture_image_path(12) == "/api/learning-space/glasses/captures/12/image"


def test_learning_sheet_read_keeps_name_when_diagram_is_missing() -> None:
    """A name with no diagram is still a result, marked failed for the diagram."""
    raw = '{"student_name": "张三", "class_name": "初一1班", "spec": {}}'
    read = parse_learning_sheet_read(raw)
    assert read.student_name == "张三"
    assert read.class_name == "初一1班"
    assert read.spec is None
    assert read.error == "spec_missing"


def test_printed_diagram_outline_lists_the_saved_nodes() -> None:
    """OCR is given the diagram already stored for the sheet."""
    outline = printed_diagram_outline(
        {
            "type": "mindmap",
            "nodes": [
                {"id": "t", "text": "桥", "type": "topic"},
                {"id": "c", "text": "拱", "type": "branch"},
            ],
            "connections": [],
        }
    )
    assert "桥" in outline
    assert "拱" in outline
    assert SHEET_OCR_MODEL == "qwen3.8-flash"


def test_learning_sheet_read_builds_a_mind_map() -> None:
    """Handwritten nodes become a topic plus children."""
    raw = '{"student_name": "李四", "class_name": "", "spec": {"topic": "细胞", "children": [{"text": "细胞膜"}]}}'
    read = parse_learning_sheet_read(raw)
    assert read.error == ""
    assert read.spec == {"topic": "细胞", "children": [{"id": "n_0_0", "text": "细胞膜"}]}


def test_a_glasses_cue_names_the_signed_in_account() -> None:
    """The course stream is one channel per account."""
    assert glasses_events_channel(3) == "mg:glasses:events:3"


def test_glasses_routes_are_mounted_on_the_learning_space_prefix() -> None:
    """Relative paths stay under /glasses so the package prefix completes the URL."""
    paths = {route.path for route in router.routes if isinstance(route, APIRoute)}
    assert "/glasses/ingest" in paths
    assert "/glasses/sheets" in paths
    assert "/glasses/sheets/copies" in paths
    assert "/glasses/captures" in paths
    assert "/glasses/captures/{capture_id}/image" in paths
    assert "/glasses/bind" in paths
    assert "/glasses/bind/unbind" in paths
    assert "/glasses/remote" in paths
    assert "/glasses/events" in paths
    assert "/glasses/device-events" in paths
