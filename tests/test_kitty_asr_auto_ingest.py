"""Fun-ASR stop must ingest the transcript when the watch never echoes text."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.ws.inbound import dispatch_kitty_ws_inbound_message
from services.kitty.ws.inbound_text import asr_utterance_already_ingested
from services.kitty.ws.inbound_types import KittyWsInboundContext


def _ctx(sid: str) -> KittyWsInboundContext:
    return KittyWsInboundContext(
        websocket=MagicMock(),
        current_user=MagicMock(id=3),
        diagram_session_id="scope-asr",
        voice_session_id=sid,
        hub_session_id="hub",
        hub=None,
        agent_session_id="agent",
        user_id="3",
    )


@pytest.mark.asyncio
async def test_asr_stop_ingests_transcript_without_client_echo() -> None:
    """asr_final with no following client text still starts a turn."""
    sid = create_voice_session(
        user_id="3",
        diagram_session_id="scope-asr",
        diagram_type="mind_map",
    )
    voice_sessions[sid]["_kitty_client_lane"] = "mobile"
    ctx = _ctx(sid)
    try:
        with (
            patch(
                "services.kitty.ws.inbound.stop_session_asr",
                new_callable=AsyncMock,
                return_value="自动补完这幅思维导图。",
            ),
            patch(
                "services.kitty.ws.inbound.safe_websocket_send",
                new_callable=AsyncMock,
            ),
            patch(
                "services.kitty.ws.inbound.fanout_voice_phase_from_outbound_type",
                new_callable=AsyncMock,
            ),
            patch(
                "services.kitty.ws.inbound.ingest_kitty_user_text",
                new_callable=AsyncMock,
                return_value="continue",
            ) as ingest,
        ):
            flow = await dispatch_kitty_ws_inbound_message(
                ctx,
                {"type": "asr_stop", "utterance_id": "w4"},
            )
            assert flow == "continue"
            ingest.assert_awaited_once()
            assert ingest.await_args is not None
            assert ingest.await_args.args[1] == "自动补完这幅思维导图。"
            fields = ingest.await_args.args[2]
            assert fields.utterance_id == "w4"
            assert fields.ingress_source == "asr"
            assert fields.cancel_prior is False
            assert asr_utterance_already_ingested(sid, "w4") is True
    finally:
        voice_sessions.pop(sid, None)


@pytest.mark.asyncio
async def test_client_text_echo_skips_already_ingested_utterance() -> None:
    """Watch text echo after asr_stop must not cancel the ingested turn."""
    sid = create_voice_session(
        user_id="3",
        diagram_session_id="scope-asr",
        diagram_type="mind_map",
    )
    voice_sessions[sid]["_kitty_client_lane"] = "mobile"
    voice_sessions[sid]["_asr_committed_utterance_id"] = "w4"
    ctx = _ctx(sid)
    try:
        with (
            patch(
                "services.kitty.ws.inbound.ingest_kitty_user_text",
                new_callable=AsyncMock,
                return_value="continue",
            ) as ingest,
            patch(
                "services.kitty.ws.inbound._interrupt_tts",
                new_callable=AsyncMock,
            ) as interrupt,
        ):
            flow = await dispatch_kitty_ws_inbound_message(
                ctx,
                {
                    "type": "text",
                    "text": "自动补完这幅思维导图。",
                    "utterance_id": "w4",
                    "ingress_source": "asr",
                },
            )
            assert flow == "continue"
            ingest.assert_not_awaited()
            interrupt.assert_not_awaited()
    finally:
        voice_sessions.pop(sid, None)
