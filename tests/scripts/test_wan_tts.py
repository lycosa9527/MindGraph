"""Wan 3 timbre clips use one qwen-audio-3.1 voice per mascot."""

from __future__ import annotations

import pytest

from scripts.sync_classroom_video.roles import ROLE_META
from scripts.training_roles.role_voices import ROLE_VOICES, lip_sync_directions, voice_for_folder
from scripts.training_roles.wan_client import (
    QWEN_AUDIO_TTS,
    WAN3_VIDEO_PRIME,
    build_tts_body,
    build_video_body,
    extract_tts_audio_url,
    with_reference_audio,
)


def test_each_mascot_has_one_qwen_audio_voice() -> None:
    """Professor is a deep male, black cat a playful boy, raven a mature woman, cats girls."""
    assert {row["folder"] for row in ROLE_VOICES} == set(ROLE_META)
    assert voice_for_folder("schnauzer-professor")["voice"] == "longsanshu_v3.1"
    assert voice_for_folder("black-cat-mascot")["voice"] == "longhuohuo_v3.1"
    assert voice_for_folder("raven-teacher-mascot")["voice"] == "wenhuaizhi_v3.1"
    assert voice_for_folder("white-cat-mascot")["voice"] == "longhua_v3.1"
    assert voice_for_folder("siamese-cat-mascot")["voice"] == "longxing_v3.1"


def test_tts_body_targets_qwen_audio_31() -> None:
    """SpeechSynthesizer requests stay on the 3.1 flash model and return a URL."""
    body = build_tts_body("同学们，看黑板。", "longsanshu_v3.1")
    assert body["model"] == QWEN_AUDIO_TTS
    assert body["input"]["voice"] == "longsanshu_v3.1"
    assert body["input"]["format"] == "wav"
    assert body["input"]["language_hints"] == ["zh"]
    payload = {
        "output": {
            "audio": {
                "url": "https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/a.wav",
            },
        },
    }
    assert extract_tts_audio_url(payload).endswith(".wav")
    assert extract_tts_audio_url({}) == ""


def test_talking_shot_passes_timbre_and_asks_for_lip_sync() -> None:
    """Wan 3 moves the mouth from reference audio. TTS does not animate the face."""
    images = [{"type": "reference_image", "url": "data:image/jpeg;base64,xx"}]
    media = with_reference_audio(images, ["https://example.com/mentor.wav", "https://example.com/black.wav"])
    directions = lip_sync_directions(["schnauzer-professor", "black-cat-mascot"])
    body = build_video_body(
        WAN3_VIDEO_PRIME,
        f"导师说：「看黑板。」黑猫说：「嘿嘿。」{directions}",
        media=media,
        audio=True,
    )
    assert [item["type"] for item in body["input"]["media"]] == [
        "reference_image",
        "reference_audio",
        "reference_audio",
    ]
    assert body["parameters"]["audio"] is True
    assert "雪纳瑞导师音色参考音频1" in directions
    assert "黑猫音色参考音频2" in directions
    assert directions.endswith("口型同步。")


def test_wan_rejects_a_sixth_timbre_clip() -> None:
    """The reference-audio cap is five clips."""
    with pytest.raises(ValueError):
        with_reference_audio([], ["https://example.com/a.wav"] * 6)
    with pytest.raises(ValueError):
        lip_sync_directions(["black-cat-mascot"] * 6)
