"""Render a script / lesson plan markdown file from manifesto steps."""

from __future__ import annotations

from typing import Any


def _setting(settings: dict[str, Any], key: str, default: str = "") -> str:
    value = str(settings.get(key) or default).strip()
    return value or default


def render_transcript_markdown(
    *,
    job_id: str,
    settings: dict[str, Any],
    steps: list[dict[str, Any]],
    diagram_id: str = "",
) -> str:
    """Human-readable script / lesson plan. Kitty speaks step captions, not this file."""
    mode = _setting(settings, "mode", "canvas_tour")
    language = _setting(settings, "language", "zh")
    lines = [
        "# Mind Classroom script / lesson plan",
        "",
        f"- job_id: {job_id}",
    ]
    cleaned_diagram = (diagram_id or "").strip()
    if cleaned_diagram:
        lines.append(f"- diagram_id: {cleaned_diagram}")
    lines.extend(
        [
            f"- mode: {mode}",
            f"- language: {language}",
            f"- mastery: {_setting(settings, 'mastery', 'first_look')}",
            f"- tone: {_setting(settings, 'tone', 'classroom')}",
            f"- audience: {_setting(settings, 'audience_level', 'general')}",
            f"- tour_scope: {_setting(settings, 'tour_scope', 'main_branch')}",
            "",
        ]
    )
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        kind = str(step.get("kind") or "branch").strip() or "branch"
        title = str(step.get("title") or "").strip() or kind
        caption = str(step.get("caption") or "").strip()
        lines.append(f"## {index}. {kind} · {title}")
        lines.append("")
        if caption:
            lines.append(caption)
            lines.append("")
        bullets = step.get("bullets")
        if isinstance(bullets, list):
            for item in bullets:
                text = str(item or "").strip()
                if text:
                    lines.append(f"- {text}")
            if any(str(item or "").strip() for item in bullets):
                lines.append("")
        focus = step.get("focus_node_ids")
        if isinstance(focus, list) and focus:
            joined = ", ".join(str(node_id).strip() for node_id in focus if str(node_id).strip())
            if joined:
                lines.append(f"<!-- focus: {joined} -->")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"
