"""Unified Kitty session memory (transcript + assistant + actions)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Literal, Optional

TurnRole = Literal["user", "assistant", "system"]
TurnSource = Literal["transcription", "text", "omni_tts", "action"]


@dataclass(slots=True)
class KittyTurn:
    role: TurnRole
    content: str
    source: TurnSource
    action_taken: Optional[str] = None
    diagram_revision: Optional[int] = None


class KittySessionMemory:
    """Single turn store per voice session (cap 20 turns)."""

    def __init__(self, *, max_turns: int = 20) -> None:
        self.turns: Deque[KittyTurn] = deque(maxlen=max_turns)
        self.diagram_snapshot_rev: int = 0
        self._assistant_buffer: List[str] = []

    def append_user_turn(self, content: str, *, source: TurnSource) -> None:
        text = content.strip()
        if not text:
            return
        self.turns.append(KittyTurn(role="user", content=text, source=source))

    def append_assistant_chunk(self, chunk: str) -> None:
        if chunk:
            self._assistant_buffer.append(chunk)

    def flush_assistant_turn(self) -> None:
        if not self._assistant_buffer:
            return
        content = "".join(self._assistant_buffer).strip()
        self._assistant_buffer.clear()
        if content:
            self.turns.append(
                KittyTurn(role="assistant", content=content, source="omni_tts")
            )

    def append_action_turn(self, summary: str, *, action: str) -> None:
        text = summary.strip()
        if not text:
            return
        self.diagram_snapshot_rev += 1
        self.turns.append(
            KittyTurn(
                role="system",
                content=text,
                source="action",
                action_taken=action,
                diagram_revision=self.diagram_snapshot_rev,
            )
        )

    def recent_turns(self, n: int = 5) -> List[KittyTurn]:
        if n <= 0:
            return []
        return list(self.turns)[-n:]

    def summarize_for_parser(self, n: int = 5) -> str:
        lines: List[str] = []
        for turn in self.recent_turns(n):
            prefix = turn.role.upper()
            if turn.action_taken:
                prefix = f"{prefix}/{turn.action_taken}"
            lines.append(f"{prefix}: {turn.content}")
        return "\n".join(lines)


_memories: Dict[str, KittySessionMemory] = {}


def get_session_memory(voice_session_id: str) -> KittySessionMemory:
    mem = _memories.get(voice_session_id)
    if mem is None:
        mem = KittySessionMemory()
        _memories[voice_session_id] = mem
    return mem


def remove_session_memory(voice_session_id: str) -> None:
    _memories.pop(voice_session_id, None)
