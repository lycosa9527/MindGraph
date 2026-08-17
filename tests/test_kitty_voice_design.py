"""Unit tests for CosyVoice v3.5 voice design helpers."""

from __future__ import annotations

import os
from typing import Any

import pytest

from services.kitty.tts.cosyvoice_realtime import resolve_runtime_model_and_voice
from services.kitty.tts.voice_design import (
    DESIGNED_VOICE_PREFIX,
    build_create_voice_payload,
    build_list_voice_payload,
    build_query_voice_payload,
    ensure_cosyvoice_designed_voice,
    locate_cosyvoice_v35_voice,
    parse_created_voice_id,
    parse_ok_voice_ids,
    parse_query_voice_ok,
    persist_kitty_tts_pin,
    reset_designed_voice_for_tests,
)


def test_list_and_create_payloads() -> None:
    """Enrollment bodies use voice-enrollment actions and the mgv35f prefix."""
    listed = build_list_voice_payload(DESIGNED_VOICE_PREFIX)
    assert listed["model"] == "voice-enrollment"
    assert listed["input"]["action"] == "list_voice"
    assert listed["input"]["prefix"] == "mgv35f"

    created = build_create_voice_payload(
        "cosyvoice-v3.5-flash",
        prefix=DESIGNED_VOICE_PREFIX,
        voice_prompt="warm teacher",
        preview_text="hello",
    )
    assert created["input"]["action"] == "create_voice"
    assert created["input"]["target_model"] == "cosyvoice-v3.5-flash"
    assert created["input"]["voice_prompt"] == "warm teacher"
    assert "url" not in created["input"]
    queried = build_query_voice_payload("cosyvoice-v3.5-flash-vd-mgv35f-x")
    assert queried["input"]["action"] == "query_voice"
    assert queried["input"]["voice_id"] == "cosyvoice-v3.5-flash-vd-mgv35f-x"
    assert parse_query_voice_ok(
        {"output": {"voice_id": "cosyvoice-v3.5-flash-vd-mgv35f-x", "status": "OK"}},
        "cosyvoice-v3.5-flash-vd-mgv35f-x",
    )
    assert not parse_query_voice_ok({"output": {"voice_id": "other", "status": "OK"}}, "wanted")


def test_parse_ok_voice_ids_skips_undeployed() -> None:
    """Only callable voice ids are reused."""
    payload: dict[str, Any] = {
        "output": {
            "voice_list": [
                {"voice_id": "dead", "status": "UNDEPLOYED"},
                {"voice_id": "live", "status": "OK"},
                {"voice_id": "", "status": "OK"},
            ]
        }
    }
    assert parse_ok_voice_ids(payload) == ["live"]


def test_parse_created_voice_id_accepts_voice_or_voice_id() -> None:
    """DashScope design responses may use voice_id or voice."""
    assert parse_created_voice_id({"output": {"voice_id": "abc"}}) == "abc"
    assert parse_created_voice_id({"output": {"voice": "xyz"}}) == "xyz"
    with pytest.raises(RuntimeError, match="no voice id"):
        parse_created_voice_id({"output": {}})
    with pytest.raises(RuntimeError, match="failed"):
        parse_created_voice_id({"message": "failed"})


@pytest.mark.asyncio
async def test_ensure_reuses_listed_voice(monkeypatch: pytest.MonkeyPatch) -> None:
    """First speak lists existing designed voices and caches the id."""
    reset_designed_voice_for_tests()

    async def fake_post(body: dict[str, Any]) -> dict[str, Any]:
        assert body["input"]["action"] == "list_voice"
        return {"output": {"voice_list": [{"voice_id": "mgv35f-existing", "status": "OK"}]}}

    monkeypatch.setattr("services.kitty.tts.voice_design._post_enrollment", fake_post)
    voice = await ensure_cosyvoice_designed_voice("cosyvoice-v3.5-flash")
    assert voice == "mgv35f-existing"
    again = await ensure_cosyvoice_designed_voice("cosyvoice-v3.5-flash")
    assert again == "mgv35f-existing"
    reset_designed_voice_for_tests()


@pytest.mark.asyncio
async def test_ensure_creates_when_list_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty list_voice creates a designed classroom voice."""
    reset_designed_voice_for_tests()
    actions: list[str] = []

    async def fake_post(body: dict[str, Any]) -> dict[str, Any]:
        action = str(body["input"]["action"])
        actions.append(action)
        if action == "list_voice":
            return {"output": {"voice_list": []}}
        return {"output": {"voice_id": "mgv35f-new"}}

    monkeypatch.setattr("services.kitty.tts.voice_design._post_enrollment", fake_post)
    voice = await ensure_cosyvoice_designed_voice("cosyvoice-v3.5-flash")
    assert voice == "mgv35f-new"
    assert actions == ["list_voice", "create_voice"]
    reset_designed_voice_for_tests()


@pytest.mark.asyncio
async def test_locate_prefers_query_then_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pinned voice_id is used when query_voice returns OK."""
    reset_designed_voice_for_tests()

    async def fake_post(body: dict[str, Any]) -> dict[str, Any]:
        assert body["input"]["action"] == "query_voice"
        return {"output": {"voice_id": "pinned-ok", "status": "OK"}}

    monkeypatch.setattr("services.kitty.tts.voice_design._post_enrollment", fake_post)
    voice = await locate_cosyvoice_v35_voice("pinned-ok", "cosyvoice-v3.5-flash")
    assert voice == "pinned-ok"
    reset_designed_voice_for_tests()


@pytest.mark.asyncio
async def test_runtime_falls_back_to_v3_when_locate_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing v3.5 voice uses cosyvoice-v3-flash + longyumi_v3."""
    reset_designed_voice_for_tests()
    monkeypatch.delenv("KITTY_TTS_VOICE", raising=False)
    monkeypatch.setenv("KITTY_TTS_MODEL", "cosyvoice-v3.5-flash")

    async def fake_locate(preferred: str, target_model: str) -> str:
        del preferred, target_model
        return ""

    monkeypatch.setattr(
        "services.kitty.tts.cosyvoice_realtime.locate_cosyvoice_v35_voice",
        fake_locate,
    )
    model, voice = await resolve_runtime_model_and_voice()
    assert model == "cosyvoice-v3-flash"
    assert voice == "longyumi_v3"
    reset_designed_voice_for_tests()


def test_persist_kitty_tts_pin_upserts_env_file(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Located v3.5 voice is written to .env and process env."""
    env_file = tmp_path / ".env"
    env_file.write_text("FEATURE_KITTY_AGENT=True\n", encoding="utf-8")
    monkeypatch.delenv("KITTY_TTS_MODEL", raising=False)
    monkeypatch.delenv("KITTY_TTS_VOICE", raising=False)
    wrote = persist_kitty_tts_pin(
        "cosyvoice-v3.5-flash",
        "cosyvoice-v3.5-flash-vd-mgv35f-test",
        env_path=env_file,
    )
    assert wrote is True
    text = env_file.read_text(encoding="utf-8")
    assert "KITTY_TTS_MODEL=cosyvoice-v3.5-flash" in text
    assert "KITTY_TTS_VOICE=cosyvoice-v3.5-flash-vd-mgv35f-test" in text
    assert os.environ["KITTY_TTS_VOICE"] == "cosyvoice-v3.5-flash-vd-mgv35f-test"
