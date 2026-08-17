"""Tests for the DashScope system-voice catalog."""

from __future__ import annotations

from services.tts.voices import (
    ALL_SYSTEM_VOICES,
    COSY_V2,
    COSY_V3_FLASH,
    COSY_V3_PLUS,
    COSY_V35_FLASH,
    FAMILY_COSYVOICE,
    FAMILY_QWEN_AUDIO,
    FAMILY_QWEN_TTS,
    get_system_voice,
    has_system_voices,
    is_system_voice,
    list_system_voices,
    list_tts_families,
    normalize_tts_model,
)


def test_three_families_and_no_duplicate_model_voice() -> None:
    """Catalog covers CosyVoice / Qwen-Audio / Qwen-TTS without pair clashes."""
    assert list_tts_families() == (FAMILY_COSYVOICE, FAMILY_QWEN_AUDIO, FAMILY_QWEN_TTS)
    seen: set[tuple[str, str]] = set()
    families = {row.family for row in ALL_SYSTEM_VOICES}
    assert families == {FAMILY_COSYVOICE, FAMILY_QWEN_AUDIO, FAMILY_QWEN_TTS}
    for row in ALL_SYSTEM_VOICES:
        assert row.voice_id
        assert row.models
        for model in row.models:
            pair = (model, row.voice_id)
            assert pair not in seen
            seen.add(pair)
    assert len(ALL_SYSTEM_VOICES) > 200


def test_cosyvoice_v35_has_no_system_voices() -> None:
    """v3.5 is design/clone only — picker should not offer longyumi_v3."""
    assert has_system_voices(COSY_V35_FLASH) is False
    assert list_system_voices(model=COSY_V35_FLASH) == ()
    assert is_system_voice(COSY_V35_FLASH, "longyumi_v3") is False


def test_cosyvoice_v3_flash_yumi_and_shared_plus() -> None:
    """YUMI is v3-flash; 龙安洋 is shared with v3-plus."""
    yumi = get_system_voice(COSY_V3_FLASH, "longyumi_v3")
    assert yumi is not None
    assert yumi.name == "YUMI"
    assert yumi.scene == "语音助手"
    assert is_system_voice(COSY_V3_PLUS, "longyumi_v3") is False
    yang = get_system_voice(COSY_V3_FLASH, "longanyang")
    assert yang is not None
    assert COSY_V3_PLUS in yang.models
    assert is_system_voice(COSY_V3_PLUS, "longanyang") is True
    assert is_system_voice(COSY_V2, "longyumi_v2") is True


def test_qwen_audio_and_qwen_tts_picker_rows() -> None:
    """Qwen-Audio plus/flash and Qwen-TTS snapshot models resolve."""
    plus = list_system_voices(model="qwen-audio-3.0-tts-plus", family=FAMILY_QWEN_AUDIO)
    assert {row.voice_id for row in plus} == {"longanlingxin", "longanlufeng"}
    flash = get_system_voice("qwen-audio-3.0-tts-flash", "longanfengyue")
    assert flash is not None
    assert flash.trait == "自然亲切音"
    cherry = get_system_voice("qwen3-tts-flash-realtime-2025-11-27", "Cherry")
    assert cherry is not None
    assert cherry.name == "芊悦"
    assert is_system_voice("qwen3-tts-flash-realtime", "cherry") is True
    assert is_system_voice("qwen3-tts-instruct-flash-realtime", "Jennifer") is False
    assert normalize_tts_model("qwen-tts-latest") == "qwen-tts"
    row = cherry.as_dict()
    assert row["voice_id"] == "Cherry"
    assert "qwen3-tts-flash-realtime" in row["models"]
