"""Static manifest for the Kitty LLMOps admin tab (modules, wiring, hub surface).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, List

from services.kitty.routing.intent_catalog import (
    KITTY_INTENT_ROWS,
    special_flows_as_json,
    voice_intent_rows_as_json,
)


def build_kitty_llmops_manifest() -> Dict[str, Any]:
    """Return JSON-serializable architecture map for ``GET /admin/kitty-llmops/architecture``."""

    diagram_voice_intents = [r["name"] for r in KITTY_INTENT_ROWS if r["kind"] == "diagram"]
    ui_voice_intents = [r["name"] for r in KITTY_INTENT_ROWS if r["kind"] == "ui"]
    mermaid_hub = (
        "flowchart LR\n"
        "  Client[Browser_WS] --> Routes[kitty_routes]\n"
        "  Routes --> HubOpen[hub_open_prepare]\n"
        "  Routes --> Inbound[ws_inbound]\n"
        "  Inbound --> Omni[OmniClient]\n"
        "  Inbound --> HubPatch[apply_kitty_ws_context_patch]\n"
        "  Omni --> Commands[route_voice_command]\n"
        "  Commands --> HubBridge[diagram_hub_bridge]\n"
        "  HubPatch --> AgentHub[MindGraphAgentHub]\n"
        "  HubBridge --> AgentHub\n"
        "  AgentHub --> Redis[(Redis_live_spec)]\n"
    )

    return {
        "version": 1,
        "hub_mutation_ops": ["replace_context", "patch_context"],
        "diagram_voice_intents": diagram_voice_intents,
        "ui_and_special_voice_intents": ui_voice_intents,
        "modules": [
            {
                "id": "ws_transport",
                "title": "Kitty WebSocket",
                "paths": [
                    "routers/features/kitty/kitty_routes.py",
                    "services/kitty/ws/realtime.py",
                    "services/kitty/ws/guards.py",
                ],
                "role": "Auth, rate limits, start frame, dual tasks (client + Omni).",
                "hub_calls": [
                    "open_session",
                    "preempt_handshake",
                    "prepare_kitty_start_context",
                    "set_kitty_runtime",
                    "register_kitty_connection",
                    "unregister_kitty_connection",
                    "close_session",
                ],
            },
            {
                "id": "inbound_dispatch",
                "title": "Inbound JSON dispatch",
                "paths": [
                    "services/kitty/ws/inbound.py",
                    "services/kitty/ws/lifecycle.py",
                ],
                "role": "audio/text/context_update/append_image/control messages.",
                "hub_calls": ["apply_diagram_spec_mutation via apply_kitty_ws_context_patch on context_update"],
            },
            {
                "id": "omni_realtime",
                "title": "Qwen Omni",
                "paths": [
                    "clients/omni_client.py",
                    "services/kitty/omni/event_loop.py",
                    "services/features/websocket_llm_middleware.py",
                ],
                "role": "Streaming audio/text; transcriptions feed command path.",
                "hub_calls": [],
            },
            {
                "id": "intent_parse",
                "title": "KittyAgent / commands",
                "paths": [
                    "services/kitty/session/agent_state.py",
                    "services/kitty/routing/command_router.py",
                    "services/kitty/diagram/hub_bridge.py",
                ],
                "role": "NL to structured action; diagram_execute + hub bridge on mutations.",
                "hub_calls": ["try_sync_voice_diagram_to_hub after diagram_execute (voice bridge)"],
            },
            {
                "id": "hub",
                "title": "MindGraphAgentHub",
                "paths": ["services/agent_hub/scope_lifecycle.py"],
                "role": "Scope binding, revision, idempotent mutations, Redis refcount.",
                "hub_calls": ["apply_diagram_spec_mutation", "MutationOp literals"],
            },
            {
                "id": "redis_pairing",
                "title": "Kitty Redis / pairing",
                "paths": [
                    "services/kitty/infra/redis/",
                    "services/kitty/infra/desktop/kitty_desktop_focus.py",
                    "services/kitty/infra/desktop/kitty_desktop_action_queue.py",
                    "services/kitty/infra/desktop/kitty_mobile_active.py",
                    "services/kitty/infra/control/",
                ],
                "role": "live_spec, sessionmeta, desktop focus hint, desktop nav queue, control pub/sub.",
                "hub_calls": ["used by hub hydrate and snapshots"],
            },
        ],
        "mermaid_flow": mermaid_hub,
        "mermaid_kitty_hub": mermaid_hub,
        "intents": voice_intent_rows_as_json(),
        "special_flows": special_flows_as_json(),
        "intent_counts": {
            "diagram_named": sum(1 for r in KITTY_INTENT_ROWS if r["kind"] == "diagram"),
            "ui_named": sum(1 for r in KITTY_INTENT_ROWS if r["kind"] == "ui"),
        },
    }


def kitty_llmops_manifest_paths() -> List[str]:
    """Flatten manifest module paths (files only; directory entries end with ``/``)."""
    manifest = build_kitty_llmops_manifest()
    paths: List[str] = []
    for module in manifest.get("modules", []):
        for raw in module.get("paths", []):
            if isinstance(raw, str) and raw.strip():
                paths.append(raw.strip())
    return paths
