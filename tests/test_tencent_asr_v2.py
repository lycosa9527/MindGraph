"""Unit tests for Tencent realtime ASR V2 signing and sentence snapshots."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, quote, unquote, urlparse

import pytest

from services.features.tencent_asr_v2 import (
    TENCENT_ASR_ENGINE_DEFAULT,
    TENCENT_ASR_ENGINE_SPEAKER,
    TENCENT_ASR_ENGINE_SPEAKER_FALLBACK,
    TencentAsrCredentials,
    TencentAsrHandshake,
    TencentAsrV2Client,
    build_tencent_asr_v2_signed_url,
    connect_tencent_asr_v2,
    format_tencent_asr_v2_sign_plain,
    is_tencent_unsupported_engine,
    load_tencent_asr_credentials,
    resolve_tencent_asr_engine,
    sign_tencent_asr_v2,
    speaker_engine_candidates,
)
from services.features.tencent_asr_v2_errors import (
    TENCENT_ASR_CATEGORY_PARAM,
    TENCENT_ASR_CATEGORY_RETRY,
    TENCENT_ASR_NO_V2_FRAME,
    TencentAsrClassifiedError,
    TencentAsrHandshakeError,
)
from services.features.tencent_asr_v2_sentences import (
    TencentAsrSentence,
    TencentAsrTranscriptStore,
    parse_speaker_context_id,
    parse_tencent_asr_sentences,
    snapshot_browser_payload,
)
from services.features.voice_notes_asr_bridge import voice_notes_diarization_enabled


def test_sign_tencent_asr_v2_known_vector() -> None:
    """HMAC-SHA1 + Base64 matches the official V2 recipe."""
    expected = base64.b64encode(hmac.new(b"unit-secret", b"plain-text", hashlib.sha1).digest()).decode("ascii")
    assert sign_tencent_asr_v2("plain-text", "unit-secret") == expected


def test_signed_url_sorts_params_and_urlencodes_signature() -> None:
    """Query keys are sorted; signature is HMAC of host+path+query without wss://."""
    credentials = TencentAsrCredentials(
        app_id="125922001",
        secret_id="AKIDtest",
        secret_key="unit-secret",
    )
    url = build_tencent_asr_v2_signed_url(
        credentials,
        TencentAsrHandshake(
            engine_model_type=TENCENT_ASR_ENGINE_SPEAKER,
            voice_id="voice-1",
            timestamp=1745932688,
            expired=1746019088,
            nonce=8743357,
            speaker_diarization=True,
        ),
    )
    parsed = urlparse(url)
    assert parsed.scheme == "wss"
    assert parsed.netloc == "asr.cloud.tencent.com"
    assert parsed.path == "/asr/v2/125922001"
    query = parse_qs(parsed.query, keep_blank_values=True)
    assert query["engine_model_type"] == [TENCENT_ASR_ENGINE_SPEAKER]
    assert query["voice_format"] == ["1"]
    assert query["needvad"] == ["1"]
    assert query["result_mod"] == ["1"]
    assert query["enable_speaker_context"] == ["1"]
    assert "speaker_diarization" not in query
    assert "speaker_context_id" not in query
    keys_without_sig = [part.split("=", 1)[0] for part in parsed.query.split("&") if not part.startswith("signature=")]
    assert keys_without_sig == sorted(keys_without_sig)
    params = {key: values[0] for key, values in query.items() if key != "signature"}
    sign_plain = format_tencent_asr_v2_sign_plain("125922001", params)
    expected = sign_tencent_asr_v2(sign_plain, "unit-secret")
    raw_sig = [part.split("=", 1)[1] for part in parsed.query.split("&") if part.startswith("signature=")][0]
    assert unquote(raw_sig) == expected
    assert raw_sig == quote(expected, safe="")


def test_signed_url_omits_speaker_context_without_diarization() -> None:
    """Non-speaker engine does not send the 24h voiceprint handshake knobs."""
    url = build_tencent_asr_v2_signed_url(
        TencentAsrCredentials(app_id="125922001", secret_id="AKIDtest", secret_key="unit-secret"),
        TencentAsrHandshake(
            engine_model_type=TENCENT_ASR_ENGINE_DEFAULT,
            voice_id="voice-plain",
            timestamp=1745932688,
            expired=1746019088,
            nonce=8743357,
            speaker_diarization=False,
            speaker_context_id="vp-ignored",
        ),
    )
    query = parse_qs(urlparse(url).query, keep_blank_values=True)
    assert "enable_speaker_context" not in query
    assert "speaker_context_id" not in query


def test_signed_url_reuses_speaker_context_id() -> None:
    """Resume query includes the 24h voiceprint id from the previous speaker task."""
    url = build_tencent_asr_v2_signed_url(
        TencentAsrCredentials(app_id="125922001", secret_id="AKIDtest", secret_key="unit-secret"),
        TencentAsrHandshake(
            engine_model_type=TENCENT_ASR_ENGINE_SPEAKER,
            voice_id="voice-2",
            timestamp=1745932688,
            expired=1746019088,
            nonce=8743357,
            speaker_diarization=True,
            speaker_context_id="vp-24h-abc",
        ),
    )
    query = parse_qs(urlparse(url).query, keep_blank_values=True)
    assert query["enable_speaker_context"] == ["1"]
    assert query["speaker_context_id"] == ["vp-24h-abc"]


def test_parse_speaker_context_id_from_v2_frame() -> None:
    """Accept the resume id from the frame or the sentences object; reject junk."""
    assert parse_speaker_context_id({"speaker_context_id": "ctx-1"}) == "ctx-1"
    assert parse_speaker_context_id({"sentences": {"speaker_context_id": "ctx-2"}}) == "ctx-2"
    assert parse_speaker_context_id({"speaker_context_id": "bad id"}) == ""
    payload = snapshot_browser_payload(
        [TencentAsrSentence("你好", 0, 0, True, 0, 100)],
        "ctx-3",
    )
    assert payload["speaker_context_id"] == "ctx-3"


def test_resolve_engine_speaker_toggle() -> None:
    """Diarization selects 16k_zh_en_speaker_2.0 from the 35682 catalog."""
    assert resolve_tencent_asr_engine(speaker_diarization=False) == TENCENT_ASR_ENGINE_DEFAULT
    assert resolve_tencent_asr_engine(speaker_diarization=True) == TENCENT_ASR_ENGINE_SPEAKER
    assert speaker_engine_candidates(speaker_diarization=False) == (TENCENT_ASR_ENGINE_DEFAULT,)
    assert speaker_engine_candidates(speaker_diarization=True) == (
        TENCENT_ASR_ENGINE_SPEAKER,
        TENCENT_ASR_ENGINE_SPEAKER_FALLBACK,
    )


def test_legacy_speaker_url_sends_diarization_flag() -> None:
    """16k_zh_en_speaker (meeting guide) needs speaker_diarization=1."""
    url = build_tencent_asr_v2_signed_url(
        TencentAsrCredentials(app_id="125922001", secret_id="AKIDtest", secret_key="unit-secret"),
        TencentAsrHandshake(
            engine_model_type=TENCENT_ASR_ENGINE_SPEAKER_FALLBACK,
            voice_id="voice-legacy",
            timestamp=1745932688,
            expired=1746019088,
            nonce=8743357,
            speaker_diarization=True,
        ),
    )
    query = parse_qs(urlparse(url).query, keep_blank_values=True)
    assert query["engine_model_type"] == [TENCENT_ASR_ENGINE_SPEAKER_FALLBACK]
    assert query["speaker_diarization"] == ["1"]
    assert query["enable_speaker_context"] == ["1"]


def test_is_tencent_unsupported_engine() -> None:
    """Only 4001 engine-not-supported is a speaker SKU fallback."""
    rejected = TencentAsrClassifiedError(
        category=TENCENT_ASR_CATEGORY_PARAM,
        message="参数不合法(Not support [engine_model_type: 16k_zh_en_speaker_2.0])",
        provider_code="4001",
    )
    other = TencentAsrClassifiedError(
        category=TENCENT_ASR_CATEGORY_PARAM,
        message="参数不合法",
        provider_code="4001",
    )
    assert is_tencent_unsupported_engine(rejected) is True
    assert is_tencent_unsupported_engine(other) is False


def test_load_credentials_requires_explicit_app_id(monkeypatch: Any) -> None:
    """COS_BUCKET is not an AppID source; TENCENT_ASR_APP_ID is required."""
    monkeypatch.delenv("TENCENT_ASR_APP_ID", raising=False)
    monkeypatch.delenv("TENCENT_ASR_SECRET_ID", raising=False)
    monkeypatch.delenv("TENCENT_ASR_SECRET_KEY", raising=False)
    monkeypatch.setenv("COS_BUCKET", "mindgraph-1356113246")
    monkeypatch.setenv("TENCENT_SMS_SECRET_ID", "sms-id")
    monkeypatch.setenv("TENCENT_SMS_SECRET_KEY", "sms-key")
    try:
        load_tencent_asr_credentials()
    except RuntimeError as exc:
        assert "TENCENT_ASR_APP_ID" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when AppID is missing")


def test_load_credentials_reuses_sms_secret_pair(monkeypatch: Any) -> None:
    """SecretId/Key reuse the SMS CAM pair; AppID is only TENCENT_ASR_APP_ID."""
    monkeypatch.setenv("TENCENT_ASR_APP_ID", "1356113246")
    monkeypatch.delenv("TENCENT_ASR_SECRET_ID", raising=False)
    monkeypatch.delenv("TENCENT_ASR_SECRET_KEY", raising=False)
    monkeypatch.setenv("TENCENT_SMS_SECRET_ID", "sms-id")
    monkeypatch.setenv("TENCENT_SMS_SECRET_KEY", "sms-key")
    loaded = load_tencent_asr_credentials()
    assert loaded.app_id == "1356113246"
    assert loaded.secret_id == "sms-id"
    assert loaded.secret_key == "sms-key"


def test_parse_sentence_list_snapshot() -> None:
    """Official SDK shape: sentences.sentence_list with speaker_id."""
    sentences = parse_tencent_asr_sentences(
        {
            "code": 0,
            "sentences": {
                "sentence_list": [
                    {
                        "sentence": "你好。",
                        "sentence_type": 1,
                        "sentence_id": 0,
                        "speaker_id": 0,
                        "start_time": 0,
                        "end_time": 800,
                    },
                    {
                        "sentence": "实时语音",
                        "sentence_type": 0,
                        "sentence_id": 1,
                        "speaker_id": -1,
                        "start_time": 900,
                        "end_time": 1400,
                    },
                ]
            },
        }
    )
    assert len(sentences) == 2
    assert sentences[0].is_final is True
    assert sentences[0].speaker_id == 0
    assert sentences[1].is_final is False
    assert sentences[1].text == "实时语音"


def test_parse_single_sentence_object() -> None:
    """API table shape: sentences is one SpeakerSentences object."""
    sentences = parse_tencent_asr_sentences(
        {
            "sentences": {
                "sentence": "实时语音识别。",
                "sentence_type": 1,
                "sentence_id": 1,
                "speaker_id": 0,
                "start_time": 1200,
                "end_time": 2850,
            }
        }
    )
    assert len(sentences) == 1
    assert sentences[0].sentence_id == 1
    payload = snapshot_browser_payload(sentences)
    assert payload["type"] == "snapshot"
    assert payload["sentences"][0]["final"] is True
    assert payload["sentences"][0]["start_time"] == 1200


def test_parse_classic_result_slice() -> None:
    """Classic realtime frames use result.voice_text_str and slice_type."""
    live = parse_tencent_asr_sentences(
        {
            "result": {
                "slice_type": 1,
                "index": 0,
                "voice_text_str": "你好",
                "start_time": 0,
                "end_time": 400,
            }
        }
    )
    assert live == [TencentAsrSentence("你好", 0, -1, False, 0, 400)]
    done = parse_tencent_asr_sentences(
        {
            "result": {
                "slice_type": 2,
                "index": 0,
                "voice_text_str": "你好。",
                "speaker_id": 0,
                "start_time": 0,
                "end_time": 800,
            }
        }
    )
    assert done[0].is_final is True
    assert done[0].speaker_id == 0


def test_transcript_store_keeps_streamed_history() -> None:
    """Each V2 message is the current sentence; the store keeps committed rows."""
    store = TencentAsrTranscriptStore()
    store.apply([TencentAsrSentence("你", 0, -1, False, 0, 200)])
    store.apply([TencentAsrSentence("你好", 0, 0, False, 0, 400)])
    first = store.apply([TencentAsrSentence("你好。", 0, 0, True, 0, 800)])
    assert [(item.text, item.is_final, item.speaker_id) for item in first] == [("你好。", True, 0)]
    growing = store.apply([TencentAsrSentence("实", 1, -1, False, 900, 1100)])
    assert [item.text for item in growing] == ["你好。", "实"]
    assert growing[1].is_final is False
    updated = store.apply([TencentAsrSentence("实时语音。", 1, 1, True, 900, 1400)])
    assert [item.text for item in updated] == ["你好。", "实时语音。"]
    assert updated[1].speaker_id == 1


def test_transcript_store_promotes_live_when_next_sentence_starts() -> None:
    """A new live line commits the previous tail if Tencent skipped type=1."""
    store = TencentAsrTranscriptStore()
    store.apply([TencentAsrSentence("第一句", 0, 0, False, 0, 500)])
    next_live = store.apply([TencentAsrSentence("第二句", 1, 1, False, 600, 900)])
    assert [(item.text, item.is_final) for item in next_live] == [
        ("第一句", True),
        ("第二句", False),
    ]


def test_transcript_store_reused_sentence_id_after_final() -> None:
    """After a stable sentence, a new live line with the same id is a new row."""
    store = TencentAsrTranscriptStore()
    store.apply([TencentAsrSentence("one", 0, 0, True, 0, 400)])
    reused = store.apply([TencentAsrSentence("two", 0, 1, False, 500, 800)])
    assert [item.text for item in reused] == ["one", "two"]
    assert reused[1].sentence_id == 1


def test_transcript_store_commit_live_on_stream_end() -> None:
    """final=1 promotes the live tail so the last words are not dropped."""
    store = TencentAsrTranscriptStore()
    store.apply([TencentAsrSentence("尾句", 2, 0, False, 2000, 2400)])
    ended = store.commit_live()
    assert ended == [TencentAsrSentence("尾句", 2, 0, True, 2000, 2400)]


def test_diarization_flag_parsing() -> None:
    """Bootstrap accepts bool / 1 / true."""
    assert voice_notes_diarization_enabled({"diarization_enabled": True}) is True
    assert voice_notes_diarization_enabled({"diarization_enabled": "true"}) is True
    assert voice_notes_diarization_enabled({"diarization_enabled": 1}) is True
    assert voice_notes_diarization_enabled({}) is False
    assert voice_notes_diarization_enabled({"diarization_enabled": "no"}) is False


def _unit_asr_credentials() -> TencentAsrCredentials:
    return TencentAsrCredentials(app_id="1356113246", secret_id="id", secret_key="key")


@pytest.mark.asyncio
async def test_connect_retries_then_succeeds() -> None:
    """A single opening-handshake timeout is retried with a new voice_id."""
    socket = AsyncMock()
    with (
        patch(
            "services.features.tencent_asr_v2.websockets.connect",
            AsyncMock(
                side_effect=[
                    TimeoutError("timed out during opening handshake"),
                    socket,
                ]
            ),
        ) as connect,
        patch("services.features.tencent_asr_v2.asyncio.sleep", new_callable=AsyncMock),
    ):
        opened, voice_id = await connect_tencent_asr_v2(
            _unit_asr_credentials(),
            speaker_diarization=True,
        )
    assert opened is socket
    assert voice_id
    assert connect.await_count == 2


@pytest.mark.asyncio
async def test_connect_timeout_becomes_handshake_error() -> None:
    """Exhausted connect retries raise a classified handshake error."""
    with (
        patch(
            "services.features.tencent_asr_v2.websockets.connect",
            AsyncMock(side_effect=TimeoutError("timed out during opening handshake")),
        ),
        patch("services.features.tencent_asr_v2.asyncio.sleep", new_callable=AsyncMock),
    ):
        try:
            await connect_tencent_asr_v2(_unit_asr_credentials(), speaker_diarization=False)
        except TencentAsrHandshakeError as exc:
            assert exc.classified.category == TENCENT_ASR_CATEGORY_RETRY
            assert exc.classified.provider_code == TENCENT_ASR_NO_V2_FRAME
        else:
            raise AssertionError("expected TencentAsrHandshakeError")


@pytest.mark.asyncio
async def test_client_falls_back_when_speaker_20_unsupported() -> None:
    """4001 engine-not-supported retries 16k_zh_en_speaker from the meeting guide."""
    first = AsyncMock()
    first.recv = AsyncMock(
        return_value=json.dumps(
            {
                "code": 4001,
                "message": "参数不合法(Not support [engine_model_type: 16k_zh_en_speaker_2.0])",
            }
        )
    )
    first.close = AsyncMock()
    second = AsyncMock()
    second.recv = AsyncMock(return_value=json.dumps({"code": 0, "message": "success"}))
    second.close = AsyncMock()

    with (
        patch(
            "services.features.tencent_asr_v2.load_tencent_asr_credentials",
            return_value=_unit_asr_credentials(),
        ),
        patch(
            "services.features.tencent_asr_v2.websockets.connect",
            AsyncMock(side_effect=[first, second]),
        ) as connect,
    ):
        client = TencentAsrV2Client(on_snapshot=AsyncMock(), speaker_diarization=True)
        await client.start()
        await client.close()

    assert connect.await_count == 2
    second_url = connect.await_args_list[1].args[0]
    assert f"engine_model_type={TENCENT_ASR_ENGINE_SPEAKER_FALLBACK}&" in second_url
    assert f"engine_model_type={TENCENT_ASR_ENGINE_SPEAKER}&" not in second_url
