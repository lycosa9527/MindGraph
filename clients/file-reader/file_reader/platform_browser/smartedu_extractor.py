"""SmartEdu lesson asset probe."""

from __future__ import annotations

from file_reader.platform_browser.models import DetectedAsset, ProbeContext
from file_reader.smartedu import metadata as smartedu_metadata
from file_reader.smartedu.url_parser import parse_smartedu_url


def smartedu_probe_status_hint(context: ProbeContext, assets: tuple[DetectedAsset, ...]) -> str:
    """Return a UI hint when SmartEdu assets cannot be detected."""
    if assets:
        return ""
    if not context.smartedu_token.strip():
        return "smartedu_token_required"
    url = context.page_url.strip()
    if not url:
        return "smartedu_lesson_required"
    try:
        parse_smartedu_url(url)
    except ValueError:
        return "smartedu_lesson_required"
    return "smartedu_lesson_not_found"


def probe_smartedu_assets(context: ProbeContext) -> tuple[DetectedAsset, ...]:
    """Fetch SmartEdu lesson assets when the page URL is parseable."""
    url = context.page_url.strip()
    if not url:
        return ()
    try:
        parsed = parse_smartedu_url(url)
        lesson = smartedu_metadata.fetch_lesson(parsed)
    except ValueError:
        return ()
    assets: list[DetectedAsset] = []
    for item in lesson.assets:
        assets.append(
            DetectedAsset(
                asset_id=item.asset_id,
                title=item.title or lesson.title,
                format_label=f"{item.alias} ({item.format.upper()})",
                platform_id="smartedu",
                extractor="smartedu",
                selected=item.selected,
                meta={
                    "smartedu_asset": item,
                    "lesson_title": lesson.title,
                    "lesson_id": lesson.lesson_id,
                },
            ),
        )
    return tuple(assets)
