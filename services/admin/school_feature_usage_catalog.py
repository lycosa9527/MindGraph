"""Module catalog and action→module mapping for school feature-usage cards.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

FEATURE_USAGE_MODULE_KEYS: tuple[str, ...] = (
    "canvas",
    "mindmate",
    "kitty",
    "voice_notes",
    "knowledge",
    "doc_summary",
    "workshop",
    "askonce",
    "debateverse",
    "markets",
    "library",
    "showcase",
    "dingtalk",
    "zhihui",
    "maite",
)

_ACTION_TO_MODULE: dict[str, str] = {
    "diagram_generate": "canvas",
    "diagram_save": "canvas",
    "export_diagram": "canvas",
    "canvas_translate": "canvas",
    "relationship_labels": "canvas",
    "autocomplete": "canvas",
    "chat_turn": "mindmate",
    "one_sentence_generate": "kitty",
    "one_sentence_edit": "kitty",
    "knowledge_query": "knowledge",
    "knowledge_ingest": "knowledge",
    "doc_summary_session": "doc_summary",
    "workshop_collab": "workshop",
    "workshop_chat": "workshop",
    "askonce_turn": "askonce",
    "debate_turn": "debateverse",
    "market_order": "markets",
    "library_engage": "library",
    "showcase_engage": "showcase",
    "dingtalk_diagram": "dingtalk",
    "t2i_image": "zhihui",
    "maite_problem": "maite",
    "maite_ocr": "maite",
    "maite_inquiry": "maite",
    "maite_diagnosis": "maite",
    "maite_remedy": "maite",
    "maite_variant": "maite",
    "maite_mentor": "maite",
    "maite_report": "maite",
}

_TOKEN_TYPE_TO_MODULE: dict[str, str] = {
    "diagram_generation": "canvas",
    "autocomplete": "canvas",
    "relationship_labels": "canvas",
    "canvas_translate": "canvas",
    "node_palette": "canvas",
    "inline_recommendations": "canvas",
    "mindmap_node_explain": "canvas",
    "mindmate": "mindmate",
    "kitty_agent_loop": "kitty",
    "one_sentence_chat": "kitty",
    "voice_command_tools": "kitty",
    "node_action_agent": "kitty",
    "voice_notes_asr": "voice_notes",
    "voice_command_parsing": "kitty",
    "voice_omni": "kitty",
    "thinkguide": "canvas",
    "concept_map_focus_validate": "canvas",
    "concept_map_focus_suggestions": "canvas",
    "knowledge_wiki": "knowledge",
    "knowledge_ingest": "knowledge",
    "askonce": "askonce",
    "debateverse": "debateverse",
    "showcase_ai_copy": "showcase",
    "showcase_ai_diagram_copy": "showcase",
    "t2i_generation": "zhihui",
    "zhihui_lesson_plan": "zhihui",
    "zhihui_wan_batch": "zhihui",
    "mind_classroom_canvas_tour": "zhihui",
    "mind_classroom_lesson_plan": "zhihui",
    "mind_classroom_wan_batch": "zhihui",
    "maite_learning": "maite",
    "kitty_agent_loop_map_gen": "kitty",
    "kitty_agent_loop_audit": "kitty",
}

DINGTALK_ENDPOINT_MARK = "generate_dingtalk"
DINGTALK_SOURCE = "dingtalk"

VOICE_NOTES_TITLE = "voice_notes"
ZHIHUI_SOURCE = "zhihui"
CAPACITY_IDLE = "idle"
CAPACITY_TENSE = "tense"
CAPACITY_AMPLE = "ample"
CAPACITY_NORMAL = "normal"
PASS_RATE_TENSE_MAX = 85.0
PASS_RATE_AMPLE_MIN = 95.0
CONCENTRATION_SHARE_MIN = 0.5
TOP_RANK_LIMIT = 5
SLOW_DURATION_FLOOR_SECONDS = 8.0
SLOW_DURATION_FLOOR_BY_MODULE: dict[str, float] = {
    "mindmate": 90.0,
    "askonce": 90.0,
    "debateverse": 90.0,
    "voice_notes": 180.0,
    "zhihui": 60.0,
    "maite": 60.0,
    "showcase": 60.0,
}


def resolve_feature_module(action: str, title: Optional[str], source: Optional[str]) -> Optional[str]:
    """Map a usage row to a catalog module. Unknown actions are dropped."""
    action_key = (action or "").strip().lower()
    source_key = (source or "").strip().lower()
    if action_key == "voice_session":
        title_key = (title or "").strip().lower()
        if title_key == VOICE_NOTES_TITLE:
            return "voice_notes"
        return "kitty"
    if source_key == DINGTALK_SOURCE:
        return "dingtalk"
    mapped = _ACTION_TO_MODULE.get(action_key)
    if mapped:
        return mapped
    if source_key == ZHIHUI_SOURCE:
        return "zhihui"
    return None


def resolve_token_module(
    request_type: Optional[str],
    endpoint_path: Optional[str] = None,
) -> Optional[str]:
    """Map token_usage request_type and endpoint to a catalog module."""
    path_key = (endpoint_path or "").strip().lower()
    if DINGTALK_ENDPOINT_MARK in path_key:
        return "dingtalk"
    type_key = (request_type or "").strip().lower()
    mapped = _TOKEN_TYPE_TO_MODULE.get(type_key)
    if mapped:
        return mapped
    if type_key.startswith("kitty_agent_loop"):
        return "kitty"
    if type_key.startswith(("mind_classroom", "zhihui_")):
        return "zhihui"
    if type_key.startswith(("concept_map", "thinkguide")):
        return "canvas"
    if type_key.startswith("voice_") and type_key != "voice_notes_asr":
        return "kitty"
    return None
