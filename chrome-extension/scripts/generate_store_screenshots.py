"""Generate Chrome Web Store listing images at exact required dimensions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_SCRIPT_DIR = Path(__file__).resolve().parent
_EXTENSION_DIR = _SCRIPT_DIR.parent
_ICONS_DIR = _EXTENSION_DIR / "icons"
_OUTPUT_DIR = _EXTENSION_DIR / "store-assets"

_SCREENSHOT_SIZE = (1280, 800)
_SMALL_PROMO_SIZE = (440, 280)
_MARQUEE_SIZE = (1400, 560)

_BG = (250, 250, 249)
_SURFACE = (255, 255, 255)
_INK = (10, 10, 10)
_INK_MUTED = (82, 82, 82)
_LINE = (231, 229, 228)
_ACCENT = (185, 28, 28)
_PANEL_BG = (250, 250, 249)

_FONT_CANDIDATES = [
    Path("/mnt/c/Windows/Fonts/segoeuib.ttf"),
    Path("/mnt/c/Windows/Fonts/segoeui.ttf"),
    Path("/mnt/c/Windows/Fonts/arialbd.ttf"),
    Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "segoeuib.ttf",
    Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
    Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "arialbd.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
]


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = _FONT_CANDIDATES if bold else _FONT_CANDIDATES[1::2]
    if bold:
        candidates = [
            Path("/mnt/c/Windows/Fonts/segoeuib.ttf"),
            Path("/mnt/c/Windows/Fonts/arialbd.ttf"),
            Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "segoeuib.ttf",
            Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "arialbd.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
        ]
    else:
        candidates = [
            Path("/mnt/c/Windows/Fonts/segoeui.ttf"),
            Path("/mnt/c/Windows/Fonts/arial.ttf"),
            Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
            Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "arial.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _hex_rgb(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return color


@dataclass(frozen=True)
class SlideSpec:
    """One Chrome Web Store screenshot composition."""

    filename: str
    headline: str
    subline: str
    active_tab: int
    panel_title: str
    panel_lead: str
    primary_button: str
    extra_lines: tuple[str, ...] = ()
    show_progress: bool = False
    progress_label: str = ""
    show_chat: bool = False


_SLIDES: tuple[SlideSpec, ...] = (
    SlideSpec(
        filename="01-mind-map.png",
        headline="Turn any web page\ninto a mind map",
        subline="One click from article to structured PNG — saved to your MindGraph library.",
        active_tab=0,
        panel_title="MindGraph",
        panel_lead="From page to structured map — one gesture.",
        primary_button="GENERATE",
        show_progress=True,
        progress_label="Generating mind map…",
    ),
    SlideSpec(
        filename="02-mindmate.png",
        headline="Ask MindMate about\nthe page you're on",
        subline="Include current page content and chat with AI using your MindGraph account.",
        active_tab=1,
        panel_title="MindMate",
        panel_lead="Chat with context from the active tab.",
        primary_button="SEND",
        show_chat=True,
        extra_lines=("Include current page content",),
    ),
    SlideSpec(
        filename="03-document-extract.png",
        headline="Download documents\nfrom education sites",
        subline="CNKI, SmartEdu, Baidu Wenku, and more — extract PDFs locally.",
        active_tab=2,
        panel_title="Download",
        panel_lead="Extract documents from supported hosts.",
        primary_button="EXTRACT DOCUMENT",
        extra_lines=("Detected: CNKI reader", "12 pages · PDF"),
    ),
    SlideSpec(
        filename="04-settings.png",
        headline="Connect with your\nMindGraph API token",
        subline="Secure Bearer auth — no web cookies. Works with production or test servers.",
        active_tab=3,
        panel_title="Settings",
        panel_lead="Server, account, and API token.",
        primary_button="SAVE",
        extra_lines=(
            "SERVER",
            "mg.mindspringedu.com",
            "API TOKEN",
            "mgat_••••••••••••",
        ),
    ),
)

_TAB_LABELS = ("Mind map", "MindMate", "Download", "Settings")


def _rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int] | None = None,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline)


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
    max_width: int,
    line_gap: int = 8,
) -> int:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y = int(bbox[3]) + line_gap
    return y


def _draw_popup_mockup(base: Image.Image, spec: SlideSpec, origin: tuple[int, int]) -> None:
    draw = ImageDraw.Draw(base)
    ox, oy = origin
    width = 400
    accent_h = 4
    tab_h = 44
    panel_pad_x = 28
    panel_pad_y = 24

    shadow = Image.new("RGB", (width + 24, 520), _BG)
    shadow_draw = ImageDraw.Draw(shadow)
    _rounded_rect(shadow_draw, (12, 8, width + 11, 511), 16, (220, 220, 218))
    base.paste(shadow, (ox - 12, oy - 8))

    popup_top = oy
    _rounded_rect(draw, (ox, popup_top, ox + width, popup_top + 500), 12, _SURFACE, _LINE)
    draw.rectangle((ox, popup_top, ox + width, popup_top + accent_h), fill=_ACCENT)

    tab_y = popup_top + accent_h
    tab_w = width // len(_TAB_LABELS)
    for index, label in enumerate(_TAB_LABELS):
        tx0 = ox + index * tab_w
        tx1 = tx0 + tab_w
        active = index == spec.active_tab
        fill = _SURFACE if active else _PANEL_BG
        draw.rectangle((tx0, tab_y, tx1, tab_y + tab_h), fill=fill)
        if active:
            draw.rectangle((tx0, tab_y + tab_h - 2, tx1, tab_y + tab_h), fill=_INK)
        font = _load_font(13, bold=active)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            (tx0 + (tab_w - tw) // 2, tab_y + (tab_h - th) // 2 - 2),
            label,
            font=font,
            fill=_INK if active else _INK_MUTED,
        )
    draw.line((ox, tab_y + tab_h, ox + width, tab_y + tab_h), fill=_LINE, width=1)

    content_y = tab_y + tab_h + panel_pad_y
    title_font = _load_font(26, bold=True)
    lead_font = _load_font(14)
    draw.text((ox + panel_pad_x, content_y), spec.panel_title, font=title_font, fill=_INK)
    title_bbox = draw.textbbox((ox + panel_pad_x, content_y), spec.panel_title, font=title_font)
    draw.text(
        (ox + panel_pad_x, title_bbox[3] + 10),
        spec.panel_lead,
        font=lead_font,
        fill=_INK_MUTED,
    )
    lead_bbox = draw.textbbox((ox + panel_pad_x, title_bbox[3] + 10), spec.panel_lead, font=lead_font)
    cursor_y = int(lead_bbox[3]) + 28

    label_font = _load_font(11, bold=True)
    hint_font = _load_font(13)
    for line in spec.extra_lines:
        if line.isupper() and len(line) < 24:
            draw.text((ox + panel_pad_x, cursor_y), line, font=label_font, fill=_INK_MUTED)
            cursor_y += 18
        else:
            field_top = cursor_y
            _rounded_rect(
                draw,
                (ox + panel_pad_x, field_top, ox + width - panel_pad_x, field_top + 36),
                18,
                _PANEL_BG,
                _LINE,
            )
            draw.text((ox + panel_pad_x + 14, field_top + 10), line, font=hint_font, fill=_INK)
            cursor_y = field_top + 48

    if spec.show_chat:
        chat_top = cursor_y
        chat_bottom = oy + 430
        _rounded_rect(
            draw,
            (ox + panel_pad_x, chat_top, ox + width - panel_pad_x, chat_bottom),
            10,
            _PANEL_BG,
            _LINE,
        )
        msg_font = _load_font(12)
        draw.text(
            (ox + panel_pad_x + 12, chat_top + 12),
            "Summarize this article in 3 bullet points.",
            font=msg_font,
            fill=_INK_MUTED,
        )
        bubble_top = chat_top + 44
        _rounded_rect(
            draw,
            (ox + panel_pad_x + 12, bubble_top, ox + width - panel_pad_x - 12, bubble_top + 72),
            8,
            _SURFACE,
            _LINE,
        )
        draw.text(
            (ox + panel_pad_x + 22, bubble_top + 12),
            "• Key idea one\n• Key idea two\n• Key idea three",
            font=msg_font,
            fill=_INK,
        )

    btn_font = _load_font(13, bold=True)
    btn_w = 180
    btn_h = 40
    btn_x = ox + (width - btn_w) // 2
    btn_y = oy + 440
    _rounded_rect(draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), 20, _INK)
    bbox = draw.textbbox((0, 0), spec.primary_button, font=btn_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        (btn_x + (btn_w - tw) // 2, btn_y + (btn_h - th) // 2 - 1),
        spec.primary_button,
        font=btn_font,
        fill=(255, 255, 255),
    )

    if spec.show_progress:
        bar_x = ox + panel_pad_x
        bar_y = btn_y - 36
        bar_w = width - panel_pad_x * 2
        _rounded_rect(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + 6), 3, _LINE)
        _rounded_rect(draw, (bar_x, bar_y, bar_x + int(bar_w * 0.62), bar_y + 6), 3, _INK)
        stage_font = _load_font(11)
        draw.text((bar_x, bar_y + 12), spec.progress_label, font=stage_font, fill=_INK_MUTED)


def _draw_browser_context(base: Image.Image, origin: tuple[int, int]) -> None:
    draw = ImageDraw.Draw(base)
    bx, by = origin
    bw, bh = 520, 340
    _rounded_rect(draw, (bx, by, bx + bw, by + bh), 10, _SURFACE, _LINE)
    chrome_h = 36
    draw.rectangle((bx, by, bx + bw, by + chrome_h), fill=(245, 245, 244))
    for index, color in enumerate(((239, 68, 68), (234, 179, 8), (34, 197, 94))):
        draw.ellipse((bx + 14 + index * 18, by + 12, bx + 24 + index * 18, by + 22), fill=color)
    url_font = _load_font(12)
    _rounded_rect(draw, (bx + 70, by + 8, bx + bw - 16, by + 28), 6, _SURFACE, _LINE)
    draw.text((bx + 82, by + 10), "https://example.com/article", font=url_font, fill=_INK_MUTED)

    article_x = bx + 28
    article_y = by + chrome_h + 24
    title_font = _load_font(20, bold=True)
    draw.text((article_x, article_y), "Sample article title", font=title_font, fill=_INK)
    for index in range(5):
        line_y = article_y + 44 + index * 22
        line_w = bw - 80 - (index % 2) * 40
        draw.rectangle((article_x, line_y, article_x + line_w, line_y + 10), fill=_LINE)


def _render_slide(spec: SlideSpec) -> Image.Image:
    img = Image.new("RGB", _SCREENSHOT_SIZE, _BG)
    draw = ImageDraw.Draw(img)

    grad = Image.new("RGB", _SCREENSHOT_SIZE, _BG)
    grad_draw = ImageDraw.Draw(grad)
    for row in range(_SCREENSHOT_SIZE[1]):
        blend = row / _SCREENSHOT_SIZE[1]
        color = (
            int(250 - 6 * blend),
            int(250 - 8 * blend),
            int(249 - 10 * blend),
        )
        grad_draw.line((0, row, _SCREENSHOT_SIZE[0], row), fill=color)
    img = grad
    draw = ImageDraw.Draw(img)

    icon_path = _ICONS_DIR / "icon128.png"
    if icon_path.is_file():
        icon = Image.open(icon_path).convert("RGBA")
        icon = icon.resize((56, 56), Image.Resampling.LANCZOS)
        img.paste(icon, (72, 56), icon)

    brand_font = _load_font(22, bold=True)
    draw.text((140, 68), "MindGraph", font=brand_font, fill=_INK)

    _draw_browser_context(img, (72, 130))
    _draw_popup_mockup(img, spec, (620, 200))

    headline_font = _load_font(52, bold=True)
    sub_font = _load_font(22)
    text_x = 72
    text_y = 500
    for line in spec.headline.split("\n"):
        draw.text((text_x, text_y), line, font=headline_font, fill=_INK)
        bbox = draw.textbbox((text_x, text_y), line, font=headline_font)
        text_y = int(bbox[3]) + 4
    text_y += 16
    _draw_text_block(draw, spec.subline, (text_x, text_y), sub_font, _INK_MUTED, 520, line_gap=10)

    return img


def _render_small_promo() -> Image.Image:
    img = Image.new("RGB", _SMALL_PROMO_SIZE, _BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, _SMALL_PROMO_SIZE[0], 4), fill=_ACCENT)
    icon_path = _ICONS_DIR / "icon128.png"
    if icon_path.is_file():
        icon = Image.open(icon_path).convert("RGBA")
        icon = icon.resize((48, 48), Image.Resampling.LANCZOS)
        img.paste(icon, (24, 28), icon)
    title_font = _load_font(20, bold=True)
    sub_font = _load_font(12)
    draw.text((84, 32), "MindGraph", font=title_font, fill=_INK)
    draw.text((84, 58), "Web → mind map", font=sub_font, fill=_INK_MUTED)
    _rounded_rect(draw, (24, 100, 416, 248), 10, _SURFACE, _LINE)
    mini = _SLIDES[0]
    mini_spec = SlideSpec(
        filename="promo.png",
        headline="",
        subline="",
        active_tab=mini.active_tab,
        panel_title=mini.panel_title,
        panel_lead=mini.panel_lead,
        primary_button=mini.primary_button,
        show_progress=True,
        progress_label="Generating…",
    )
    _draw_popup_mockup(img, mini_spec, (48, 108))
    return img


def _save_rgb_image(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = image.convert("RGB")
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        rgb.save(path, "JPEG", quality=92, optimize=True)
    else:
        rgb.save(path, "PNG")


def _assert_dimensions(path: Path, expected: tuple[int, int]) -> None:
    with Image.open(path) as opened:
        if opened.size != expected:
            raise RuntimeError(f"{path.name}: expected {expected}, got {opened.size}")
        if opened.mode not in {"RGB", "L"}:
            raise RuntimeError(f"{path.name}: expected RGB, got {opened.mode}")


def main() -> None:
    """Write store listing images and print dimensions for verification."""
    screenshots_dir = _OUTPUT_DIR / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for spec in _SLIDES:
        slide = _render_slide(spec)
        png_path = screenshots_dir / spec.filename
        jpg_path = png_path.with_suffix(".jpg")
        _save_rgb_image(slide, png_path)
        _save_rgb_image(slide, jpg_path)
        _assert_dimensions(png_path, _SCREENSHOT_SIZE)
        _assert_dimensions(jpg_path, _SCREENSHOT_SIZE)
        written.extend((png_path, jpg_path))

    promo = _render_small_promo()
    promo_path = _OUTPUT_DIR / "small-promo-tile.jpg"
    _save_rgb_image(promo, promo_path)
    _assert_dimensions(promo_path, _SMALL_PROMO_SIZE)
    written.append(promo_path)

    print(f"Wrote {len(written)} store images to {_OUTPUT_DIR}:")
    for path in written:
        with Image.open(path) as opened:
            print(f"  {path.relative_to(_EXTENSION_DIR)}  {opened.size[0]}x{opened.size[1]} {opened.mode}")


if __name__ == "__main__":
    main()
