"""URL contract for the glasses learning-sheet proof of concept.

The glasses app has no browser origin. This pass posts only to the test server.
The teacher site uses the same paths on whatever host it is already open on.
"""

from __future__ import annotations

import re

GLASSES_POC_ORIGIN = "https://test.mindspringedu.com"
SHEET_PAYLOAD_PREFIX = "mg://sheet/"
PLAY_PATH = "/api/learning-space/glasses/play"
SHEETS_PATH = "/api/learning-space/glasses/sheets"
CAPTURES_PATH = "/api/learning-space/glasses/captures"
INGEST_PATH = "/api/learning-space/glasses/ingest"
REMOTE_PATH = "/api/learning-space/glasses/remote"
SENT_DISPLAY = "学生图示已发送"
BIND_DISPLAY = "智能设备已绑定"
MAX_INGEST_BYTES = 8 * 1024 * 1024
REMOTE_ACTIONS = (
    "pan_left",
    "pan_right",
    "pan_up",
    "pan_down",
    "zoom_in",
    "zoom_out",
    "fit",
)
REMOTE_DISPLAY = {
    "pan_left": "向左",
    "pan_right": "向右",
    "pan_up": "向上",
    "pan_down": "向下",
    "zoom_in": "放大",
    "zoom_out": "缩小",
    "fit": "适应画面",
}


_SHEET_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def sheet_payload(sheet_id: str, seq: int = 0) -> str:
    """QR text. A class copy appends its sequence, ``mg://sheet/{uuid}/{seq}``."""
    base = f"{SHEET_PAYLOAD_PREFIX}{sheet_id}"
    if int(seq) > 0:
        return f"{base}/{int(seq)}"
    return base


def parse_sheet_payload(payload: str) -> tuple[str, int]:
    """Return the sheet UUID and copy sequence. Sequence 0 is the shared sheet."""
    text = (payload or "").strip()
    if text.startswith(SHEET_PAYLOAD_PREFIX):
        text = text[len(SHEET_PAYLOAD_PREFIX) :].strip()
    seq = 0
    if "/" in text:
        head, tail = text.split("/", 1)
        if not tail.isdigit() or int(tail) < 1:
            return "", 0
        text = head
        seq = int(tail)
    if not _SHEET_UUID.match(text):
        return "", 0
    return text, seq


def sheet_id_from_payload(payload: str) -> str:
    """Return the UUID from a QR payload, or an empty string when it does not match."""
    sheet_id, _seq = parse_sheet_payload(payload)
    return sheet_id


def normalize_remote_action(action: str) -> str:
    """Return a known canvas-remote action, or an empty string."""
    text = (action or "").strip()
    if text not in REMOTE_ACTIONS:
        return ""
    return text


def glasses_ingest_url() -> str:
    """Absolute ingest URL the glasses app calls during this proof of concept."""
    return f"{GLASSES_POC_ORIGIN}{INGEST_PATH}"


def capture_image_path(capture_id: int) -> str:
    """Teacher-site path for the original photo."""
    return f"{CAPTURES_PATH}/{int(capture_id)}/image"
