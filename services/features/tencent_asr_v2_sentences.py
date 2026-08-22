"""Parse and accumulate Tencent realtime ASR V2 streamed sentences.

Contract: https://cloud.tencent.com/document/api/1093/131127

Each recognition frame is the *current* sentence (or a short ``sentence_list``),
not the full transcript. ``sentence_type`` 0 is unstable (live); 1 is committed.
``sentence_id`` starts at 0 and increments when a sentence becomes stable.
``speaker_id`` starts at -1 until diarization assigns 0–9.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class TencentAsrSentence:
    """One V2 sentence after a streamed frame is parsed."""

    text: str
    sentence_id: int
    speaker_id: int
    is_final: bool
    start_time: int
    end_time: int


def _int_field(raw: Any, default: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _sentence_from_dict(item: dict[str, Any]) -> Optional[TencentAsrSentence]:
    text = str(item.get("sentence") or item.get("text") or "").strip()
    if not text:
        return None
    sentence_type = _int_field(item.get("sentence_type"), 0)
    return TencentAsrSentence(
        text=text,
        sentence_id=_int_field(item.get("sentence_id"), 0),
        speaker_id=_int_field(item.get("speaker_id"), -1),
        is_final=sentence_type == 1,
        start_time=_int_field(item.get("start_time"), 0),
        end_time=_int_field(item.get("end_time"), 0),
    )


def _classic_result_as_dict(result: dict[str, Any]) -> Optional[dict[str, Any]]:
    text = str(result.get("voice_text_str") or result.get("text") or "").strip()
    if not text:
        return None
    slice_type = _int_field(result.get("slice_type"), 1)
    return {
        "sentence": text,
        "sentence_id": _int_field(result.get("index"), 0),
        "sentence_type": 1 if slice_type == 2 else 0,
        "speaker_id": _int_field(result.get("speaker_id"), -1),
        "start_time": _int_field(result.get("start_time"), 0),
        "end_time": _int_field(result.get("end_time"), 0),
    }


def _extract_sentence_dicts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("sentences")
    if isinstance(raw, dict):
        listed = raw.get("sentence_list")
        if isinstance(listed, list):
            return [item for item in listed if isinstance(item, dict)]
        if raw.get("sentence") or raw.get("text"):
            return [raw]
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    result = payload.get("result")
    if isinstance(result, dict):
        mapped = _classic_result_as_dict(result)
        return [mapped] if mapped is not None else []
    return []


_SPEAKER_CONTEXT_KEYS = ("speaker_context_id", "speaker_context", "SpeakerContextId")
_SPEAKER_CONTEXT_ID_MAX = 128


def normalize_speaker_context_id(raw: object) -> str:
    """Keep Tencent voiceprint resume ids (24h) when they are safe query values."""
    if not isinstance(raw, str):
        return ""
    value = raw.strip()
    if not value or len(value) > _SPEAKER_CONTEXT_ID_MAX:
        return ""
    for char in value:
        if char.isalnum() or char in "._-:":
            continue
        return ""
    return value


def parse_speaker_context_id(payload: dict[str, Any]) -> str:
    """Read ``speaker_context_id`` from a V2 frame or ``sentences`` object."""
    for key in _SPEAKER_CONTEXT_KEYS:
        parsed = normalize_speaker_context_id(payload.get(key))
        if parsed:
            return parsed
    nested = payload.get("sentences")
    if isinstance(nested, dict):
        for key in _SPEAKER_CONTEXT_KEYS:
            parsed = normalize_speaker_context_id(nested.get(key))
            if parsed:
                return parsed
    return ""


def parse_tencent_asr_sentences(payload: dict[str, Any]) -> list[TencentAsrSentence]:
    """Parse ``sentences`` (131127 / speaker SDK) or classic ``result`` frames."""
    parsed: list[TencentAsrSentence] = []
    for item in _extract_sentence_dicts(payload):
        sentence = _sentence_from_dict(item)
        if sentence is not None:
            parsed.append(sentence)
    return parsed


def snapshot_browser_payload(
    sentences: list[TencentAsrSentence],
    speaker_context_id: str = "",
) -> dict[str, Any]:
    """Full accumulated transcript for the browser (replace-render)."""
    payload: dict[str, Any] = {
        "type": "snapshot",
        "sentences": [
            {
                "text": item.text,
                "speaker_id": item.speaker_id,
                "sentence_id": item.sentence_id,
                "final": item.is_final,
                "start_time": item.start_time,
                "end_time": item.end_time,
            }
            for item in sentences
        ],
    }
    context_id = normalize_speaker_context_id(speaker_context_id)
    if context_id:
        payload["speaker_context_id"] = context_id
    return payload


def _same_live_span(left: TencentAsrSentence, right: TencentAsrSentence) -> bool:
    if left.start_time > 0 and left.start_time == right.start_time:
        return True
    return left.sentence_id == right.sentence_id and right.start_time <= left.end_time


class TencentAsrTranscriptStore:
    """Committed sentences plus one live tail.

    Frames are applied in order. A new live sentence promotes the previous live
    row so history is never dropped when Tencent only sends the current line.
    """

    def __init__(self) -> None:
        self._committed: dict[int, TencentAsrSentence] = {}
        self._live: Optional[TencentAsrSentence] = None

    def apply(self, incoming: list[TencentAsrSentence]) -> list[TencentAsrSentence]:
        """Fold streamed frames into the store and return the display snapshot."""
        for item in incoming:
            self._apply_one(item)
        return self.snapshot()

    def commit_live(self) -> list[TencentAsrSentence]:
        """Promote the live tail (stream ``final=1`` or client stop)."""
        if self._live is not None:
            self._commit(self._live)
            self._live = None
        return self.snapshot()

    def snapshot(self) -> list[TencentAsrSentence]:
        """Committed rows in time order, then the live tail if present."""
        rows = list(self._committed.values())
        rows.sort(key=lambda item: (item.start_time, item.sentence_id))
        if self._live is not None:
            rows.append(self._live)
        return rows

    def _apply_one(self, item: TencentAsrSentence) -> None:
        if item.is_final:
            self._apply_final(item)
            return
        self._apply_live(item)

    def _apply_final(self, item: TencentAsrSentence) -> None:
        slot = item.sentence_id
        if self._live is not None and _same_live_span(self._live, item):
            slot = self._live.sentence_id
            self._live = None
        self._committed[slot] = TencentAsrSentence(
            text=item.text,
            sentence_id=slot,
            speaker_id=item.speaker_id,
            is_final=True,
            start_time=item.start_time,
            end_time=item.end_time,
        )

    def _apply_live(self, item: TencentAsrSentence) -> None:
        if self._live is not None and _same_live_span(self._live, item):
            self._live = TencentAsrSentence(
                text=item.text,
                sentence_id=self._live.sentence_id,
                speaker_id=item.speaker_id,
                is_final=False,
                start_time=item.start_time,
                end_time=item.end_time,
            )
            return
        prior = self._committed.get(item.sentence_id)
        if prior is not None and self._is_stale_partial(prior, item):
            return
        if self._live is not None:
            self._commit(self._live)
        self._live = self._unique_live(item)

    def _is_stale_partial(self, prior: TencentAsrSentence, item: TencentAsrSentence) -> bool:
        if item.start_time > 0 and item.start_time == prior.start_time:
            return True
        if item.start_time > prior.end_time:
            return False
        return prior.text.startswith(item.text) or item.text.startswith(prior.text)

    def _unique_live(self, item: TencentAsrSentence) -> TencentAsrSentence:
        if item.sentence_id not in self._committed:
            return item
        next_id = max(self._committed) + 1
        return TencentAsrSentence(
            text=item.text,
            sentence_id=next_id,
            speaker_id=item.speaker_id,
            is_final=False,
            start_time=item.start_time,
            end_time=item.end_time,
        )

    def _commit(self, item: TencentAsrSentence) -> None:
        self._committed[item.sentence_id] = TencentAsrSentence(
            text=item.text,
            sentence_id=item.sentence_id,
            speaker_id=item.speaker_id,
            is_final=True,
            start_time=item.start_time,
            end_time=item.end_time,
        )
