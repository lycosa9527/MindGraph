"""Static manifest for the Kitty LLMOps admin tab (modules, wiring, hub surface)."""

from __future__ import annotations

from typing import Any, Dict

from services.kitty_voice.voice_intent_catalog import (
    KITTY_VOICE_INTENT_ROWS,
    special_flows_as_json,
    voice_intent_rows_as_json,
)


def build_kitty_llmops_manifest() -> Dict[str, Any]:
    """Return JSON-serializable architecture map for ``GET /admin/kitty-llmops/architecture``."""

    diagram_voice_intents = [r["name"] for r in KITTY_VOICE_INTENT_ROWS if r["kind"] == "diagram"]
    ui_voice_intents = [r["name"] for r in KITTY_VOICE_INTENT_ROWS if r["kind"] == "ui"]
    mermaid_hub = (
        "flowchart LR\n"
        "  Client[Browser_WS] --> Routes[kitty_routes]\n"
        "  Routes --> HubOpen[hub_open_prepare]\n"
        "  Routes --> Inbound[kitty_ws_inbound_or_pipecat]\n"
        "  Inbound --> Omni[OmniClient]\n"
        "  Inbound --> HubPatch[apply_kitty_ws_context_patch]\n"
        "  Omni --> Commands[process_voice_command]\n"
        "  Commands --> HubBridge[diagram_voice_hub_bridge]\n"
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
                    "routers/features/voice/kitty_routes.py",
                    "services/kitty_voice/kitty_realtime_websocket.py",
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
                    "services/kitty_voice/kitty_ws_inbound.py",
                    "services/kitty_voice/pipecat_kitty/session.py (optional)",
                ],
                "role": "audio/text/context_update/append_image/control messages.",
                "hub_calls": ["apply_diagram_spec_mutation via apply_kitty_ws_context_patch on context_update"],
            },
            {
                "id": "omni_realtime",
                "title": "Qwen Omni",
                "paths": ["clients/omni_client.py", "services/features/websocket_llm_middleware.py"],
                "role": "Streaming audio/text; transcriptions feed command path.",
                "hub_calls": [],
            },
            {
                "id": "intent_parse",
                "title": "KittyAgent / commands",
                "paths": [
                    "services/features/voice_agent.py",
                    "routers/features/voice/commands.py",
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
                    "services/kitty/",
                    "services/kitty/kitty_desktop_focus.py (pairing hint only)",
                    "services/kitty/kitty_desktop_action_queue.py (open_canvas nav only)",
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
            "diagram_named": sum(1 for r in KITTY_VOICE_INTENT_ROWS if r["kind"] == "diagram"),
            "ui_named": sum(1 for r in KITTY_VOICE_INTENT_ROWS if r["kind"] == "ui"),
        },
    }
