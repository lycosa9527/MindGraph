"""Canonical earn-task wiring manifest for audit tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from utils.auth.thinking_coin_config import (
    EVENT_DIAGRAM_EXPORT,
    EVENT_DIAGRAM_SAVE,
    EVENT_DIAGRAM_SNAPSHOT,
    EVENT_DIAGRAM_TRANSLATE,
    EVENT_LEARNING_SHEET,
    EVENT_MINDMATE_SHARE,
    EVENT_WORKSHOP_JOIN,
    HANDLER_AUTO_LOGIN,
    HANDLER_CLIENT_EVENT,
    HANDLER_NAVIGATE,
    HANDLER_REFERRAL,
    HANDLER_USAGE_DAILY,
    SLUG_DAILY_CHECKIN,
    SLUG_DAILY_DIAGRAM,
    SLUG_DAILY_DIAGRAM_EXPORT,
    SLUG_DAILY_DIAGRAM_SAVE,
    SLUG_DAILY_DIAGRAM_SNAPSHOT,
    SLUG_DAILY_DIAGRAM_TRANSLATE,
    SLUG_DAILY_LEARNING_SHEET,
    SLUG_DAILY_LEARNING_SHEET_AI,
    SLUG_DAILY_MINDMATE,
    SLUG_DAILY_MINDMATE_SHARE,
    SLUG_DAILY_WORKSHOP_JOIN,
    SLUG_PUBLISH_CASE,
    SLUG_REFERRAL,
)


@dataclass(frozen=True)
class TaskWiring:
    """Expected runtime wiring for one earn task."""

    slug: str
    handler_key: str
    credits_on_complete: bool
    backend_markers: tuple[str, ...]
    frontend_markers: tuple[str, ...] = ()
    event_key: str | None = None
    request_type: str | None = None
    note: str = ""


ALL_SEEDED_SLUGS: Final[frozenset[str]] = frozenset(
    {
        SLUG_DAILY_CHECKIN,
        SLUG_DAILY_MINDMATE,
        SLUG_DAILY_DIAGRAM,
        SLUG_REFERRAL,
        SLUG_PUBLISH_CASE,
        SLUG_DAILY_MINDMATE_SHARE,
        SLUG_DAILY_DIAGRAM_EXPORT,
        SLUG_DAILY_LEARNING_SHEET,
        SLUG_DAILY_DIAGRAM_SAVE,
        SLUG_DAILY_DIAGRAM_TRANSLATE,
        SLUG_DAILY_DIAGRAM_SNAPSHOT,
        SLUG_DAILY_WORKSHOP_JOIN,
        SLUG_DAILY_LEARNING_SHEET_AI,
    }
)

TASK_WIRING: Final[tuple[TaskWiring, ...]] = (
    TaskWiring(
        slug=SLUG_DAILY_CHECKIN,
        handler_key=HANDLER_AUTO_LOGIN,
        credits_on_complete=True,
        backend_markers=(
            "try_daily_checkin",
            "ensure_wallet_bootstrap",
            "track_checkin",
        ),
        frontend_markers=("/api/auth/thinking-coins/check-in",),
    ),
    TaskWiring(
        slug=SLUG_DAILY_MINDMATE,
        handler_key=HANDLER_USAGE_DAILY,
        credits_on_complete=True,
        request_type="mindmate",
        backend_markers=(
            "thinking_coin_post_llm_success_mutation",
            "try_daily_activity_earn",
        ),
        frontend_markers=("applyThinkingCoinMutation", "useMindMate.ts"),
    ),
    TaskWiring(
        slug=SLUG_DAILY_DIAGRAM,
        handler_key=HANDLER_USAGE_DAILY,
        credits_on_complete=True,
        request_type="diagram_generation",
        backend_markers=(
            "thinking_coin_post_llm_success_mutation",
            "try_daily_activity_earn",
        ),
        frontend_markers=("generateGraphStream.ts",),
    ),
    TaskWiring(
        slug=SLUG_DAILY_MINDMATE_SHARE,
        handler_key=HANDLER_CLIENT_EVENT,
        credits_on_complete=True,
        event_key=EVENT_MINDMATE_SHARE,
        backend_markers=("post_claim_event", "thinking_coin_config"),
        frontend_markers=("claimThinkingCoinEvent('mindmate_share')", "ShareExportModal.vue"),
    ),
    TaskWiring(
        slug=SLUG_DAILY_DIAGRAM_EXPORT,
        handler_key=HANDLER_CLIENT_EVENT,
        credits_on_complete=True,
        event_key=EVENT_DIAGRAM_EXPORT,
        backend_markers=("track_client_event", "EVENT_DIAGRAM_EXPORT"),
        frontend_markers=("useDiagramExport.ts",),
    ),
    TaskWiring(
        slug=SLUG_DAILY_LEARNING_SHEET,
        handler_key=HANDLER_CLIENT_EVENT,
        credits_on_complete=True,
        event_key=EVENT_LEARNING_SHEET,
        backend_markers=("post_claim_event", "thinking_coin_config"),
        frontend_markers=("claimThinkingCoinEvent('learning_sheet_enable')",),
    ),
    TaskWiring(
        slug=SLUG_DAILY_DIAGRAM_SAVE,
        handler_key=HANDLER_CLIENT_EVENT,
        credits_on_complete=True,
        event_key=EVENT_DIAGRAM_SAVE,
        backend_markers=("track_client_event", "EVENT_DIAGRAM_SAVE"),
        frontend_markers=("savedDiagrams.ts",),
    ),
    TaskWiring(
        slug=SLUG_DAILY_DIAGRAM_TRANSLATE,
        handler_key=HANDLER_CLIENT_EVENT,
        credits_on_complete=True,
        event_key=EVENT_DIAGRAM_TRANSLATE,
        backend_markers=(
            "_claim_diagram_translate_earn",
            "EVENT_DIAGRAM_TRANSLATE",
        ),
        frontend_markers=("useCanvasToolbarApps.ts",),
    ),
    TaskWiring(
        slug=SLUG_DAILY_DIAGRAM_SNAPSHOT,
        handler_key=HANDLER_CLIENT_EVENT,
        credits_on_complete=True,
        event_key=EVENT_DIAGRAM_SNAPSHOT,
        backend_markers=("track_client_event", "EVENT_DIAGRAM_SNAPSHOT"),
        frontend_markers=("useSnapshotHistory.ts",),
    ),
    TaskWiring(
        slug=SLUG_DAILY_WORKSHOP_JOIN,
        handler_key=HANDLER_CLIENT_EVENT,
        credits_on_complete=True,
        event_key=EVENT_WORKSHOP_JOIN,
        backend_markers=(
            "track_client_event",
            "EVENT_WORKSHOP_JOIN",
            "load_user_org(current_user)",
        ),
        frontend_markers=("MindGraphCollabPanel.vue", "MindmateCollabPanel.vue"),
    ),
    TaskWiring(
        slug=SLUG_DAILY_LEARNING_SHEET_AI,
        handler_key=HANDLER_USAGE_DAILY,
        credits_on_complete=True,
        request_type="diagram_generation",
        backend_markers=(
            "thinking_coin_post_diagram_generation_mutation",
            "try_learning_sheet_diagram_earn",
            "is_learning_sheet",
        ),
        frontend_markers=("generateGraphStream.ts",),
    ),
    TaskWiring(
        slug=SLUG_PUBLISH_CASE,
        handler_key=HANDLER_NAVIGATE,
        credits_on_complete=False,
        backend_markers=("SLUG_PUBLISH_CASE", "coming_soon"),
        frontend_markers=("publish_case",),
        note="Navigate-only; moderation credit path not implemented",
    ),
    TaskWiring(
        slug=SLUG_REFERRAL,
        handler_key=HANDLER_REFERRAL,
        credits_on_complete=False,
        backend_markers=(SLUG_REFERRAL,),
        note="Seeded inactive until invite attribution exists",
    ),
)

CLIENT_EVENT_TASKS: Final[tuple[TaskWiring, ...]] = tuple(
    task for task in TASK_WIRING if task.handler_key == HANDLER_CLIENT_EVENT
)

USAGE_DAILY_TASKS: Final[tuple[TaskWiring, ...]] = tuple(
    task for task in TASK_WIRING if task.handler_key == HANDLER_USAGE_DAILY
)
