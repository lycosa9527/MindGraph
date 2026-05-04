"""Bulk-insert collab i18n keys into locale canvas.ts and workshop.ts files."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend" / "src" / "locales" / "messages"

CANVAS_BLOCK = (
    "  'canvasPage.collabConnected': 'Connected',\n"
    "  'canvas.topBar.viewOnly': 'View only',\n"
    "  'canvasPage.collabParticipantsMore': 'more',\n"
)
WORKSHOP_BLOCK = (
    "  'workshopCanvas.otherTabCollaborationActive': "
    "'Collaboration continues in another tab or window for this account.',\n"
    "  'workshopCanvas.joinQrAlt': 'Join collaboration QR code',\n"
)


def patch_canvas(canvas: Path) -> None:
    try:
        text = canvas.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"canvas decode skip: {canvas.parent.name}")
        return
    if "canvasPage.collabConnected" in text:
        return
    key = "'canvasPage.collabParticipantsAria':"
    pos = text.find(key)
    if pos == -1:
        print(f"canvas skip (no aria): {canvas.parent.name}")
        return
    line_end = text.find("\n", pos)
    if line_end == -1:
        print(f"canvas bad: {canvas}")
        return
    insert_at = line_end + 1
    canvas.write_text(text[:insert_at] + CANVAS_BLOCK + text[insert_at:], encoding="utf-8")


def patch_workshop(wsh: Path) -> None:
    raw = wsh.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    if "workshopCanvas.joinQrAlt" in text:
        return
    idx = text.rfind("\n}")
    if idx == -1:
        print(f"workshop skip: {wsh.parent.name}")
        return
    inner = text[:idx] + "\n" + WORKSHOP_BLOCK + text[idx + 1 :]
    wsh.write_text(inner, encoding="utf-8")

def main() -> None:
    for canvas in sorted(ROOT.glob("*/canvas.ts")):
        try:
            patch_canvas(canvas)
        except OSError as exc:
            print(canvas, exc)

    for wsh in sorted(ROOT.glob("*/workshop.ts")):
        try:
            patch_workshop(wsh)
        except OSError as exc:
            print(wsh, exc)


if __name__ == "__main__":
    main()
