"""Knowledge Wiki compile prompts (File Center v2a).

When a source is added to a File Center package, an LLM compiles or updates a
small set of markdown "wiki" pages for that package (overview + topic pages).
These pages are an additive knowledge layer on top of chunk RAG; the raw
chunks remain the ground truth.

The compiler sends the existing wiki index plus a summary of the newly indexed
source and expects a strict JSON object describing page create/update actions.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import List

# JSON schema the model must return. Shared across locales so parsing is stable.
_WIKI_OUTPUT_SCHEMA = """Return ONLY valid JSON, no markdown fences, with this exact shape:

{
  "pages": [
    {
      "action": "create" | "update",
      "slug": "overview",
      "title": "Overview",
      "body_md": "Markdown body of the page (concise notes, headings, bullets).",
      "links": [{"slug": "chapter-5", "label": "Convolutional Networks"}]
    }
  ]
}

Rules:
- Always include or update the "overview" page summarizing the whole package.
- Create one topic page per major heading/chapter detected in the new source.
- "slug" is lowercase, hyphenated, ASCII, stable across runs (reuse existing slugs to update).
- Keep each body under ~400 words; these are compiled notes, not transcripts.
- Only return pages that changed; do not restate unchanged pages.
- "links" may be empty.
"""

KNOWLEDGE_WIKI_COMPILE_SYSTEM_EN = (
    "You are a knowledge wiki compiler. You maintain a compact set of markdown "
    "notes for a research package made of multiple sources. Given the existing "
    "wiki pages and a newly added source, you update the overview and create or "
    "revise topic pages so the package reads as one coherent, cross-linked wiki.\n\n" + _WIKI_OUTPUT_SCHEMA
)

KNOWLEDGE_WIKI_COMPILE_SYSTEM_ZH = (
    "你是一个知识维基编译器。你为由多个来源组成的研究资料包维护一组精简的 Markdown 笔记。"
    "给定现有的维基页面和新加入的来源，你需要更新总览页，并创建或修订主题页，"
    "使整个资料包成为一份连贯且相互链接的维基。\n\n" + _WIKI_OUTPUT_SCHEMA
)


def build_wiki_compile_user_prompt(
    package_name: str,
    existing_index: List[dict],
    new_source_title: str,
    new_source_text: str,
    language: str = "en",
) -> str:
    """Build the user prompt for a single package wiki compile pass.

    Args:
        package_name: Human name of the package.
        existing_index: List of ``{"slug","title"}`` for current wiki pages.
        new_source_title: Title of the newly indexed source.
        new_source_text: Representative text from the new source (already capped).
        language: ``"zh"`` or ``"en"`` — controls section labels only.
    """
    if existing_index:
        index_lines = "\n".join(f"- {page.get('slug')}: {page.get('title')}" for page in existing_index)
    else:
        index_lines = "(none yet)"

    if language.startswith("zh"):
        return (
            f"资料包名称：{package_name}\n\n"
            f"现有维基页面（slug: 标题）：\n{index_lines}\n\n"
            f"新加入来源标题：{new_source_title}\n\n"
            f"新来源内容（节选）：\n{new_source_text}\n\n"
            "请据此输出需要创建或更新的维基页面（JSON）。"
        )
    return (
        f"Package name: {package_name}\n\n"
        f"Existing wiki pages (slug: title):\n{index_lines}\n\n"
        f"Newly added source title: {new_source_title}\n\n"
        f"New source content (excerpt):\n{new_source_text}\n\n"
        "Output the wiki pages to create or update as JSON."
    )
