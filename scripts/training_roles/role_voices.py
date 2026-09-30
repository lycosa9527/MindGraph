"""Qwen-Audio-TTS voices for the five mascot roles.

Wan 3.0 lip-syncs when these clips are passed as ``reference_audio``.
The model copies each timbre and moves that role's mouth. Qwen TTS
does not animate the face. At most five clips, and their durations
must add up to 15 seconds or less.
"""

from __future__ import annotations

from typing import TypedDict


class RoleVoice(TypedDict):
    """One mascot and the qwen-audio-3.1-tts-flash system voice that speaks for it."""

    folder: str
    label: str
    voice: str
    trait: str


ROLE_VOICES: tuple[RoleVoice, ...] = (
    {
        "folder": "schnauzer-professor",
        "label": "雪纳瑞导师",
        "voice": "longsanshu_v3.1",
        "trait": "沉稳质感男声",
    },
    {
        "folder": "black-cat-mascot",
        "label": "黑猫",
        "voice": "longhuohuo_v3.1",
        "trait": "顽皮少年音",
    },
    {
        "folder": "raven-teacher-mascot",
        "label": "乌鸦",
        "voice": "wenhuaizhi_v3.1",
        "trait": "稳重成熟女声",
    },
    {
        "folder": "white-cat-mascot",
        "label": "白猫",
        "voice": "longhua_v3.1",
        "trait": "元气甜美女声",
    },
    {
        "folder": "siamese-cat-mascot",
        "label": "暹罗猫",
        "voice": "longxing_v3.1",
        "trait": "温婉邻家女声",
    },
)

MAX_REFERENCE_AUDIO = 5


def voice_for_folder(folder: str) -> RoleVoice:
    """Return the system voice bound to one mascot folder."""
    for row in ROLE_VOICES:
        if row["folder"] == folder:
            return row
    raise KeyError(folder)


def lip_sync_directions(folders: list[str]) -> str:
    """Bind each role to 音频N and ask Wan 3 to move that mouth.

    ``folders`` must follow the ``reference_audio`` order. 音频1 is the
    first audio item, independent of where the images sit in ``media``.
    """
    if len(folders) > MAX_REFERENCE_AUDIO:
        raise ValueError(f"Wan 3 accepts at most {MAX_REFERENCE_AUDIO} reference audio clips")
    parts = []
    for index, folder in enumerate(folders, start=1):
        row = voice_for_folder(folder)
        parts.append(f"{row['label']}音色参考音频{index}")
    parts.append("口型同步")
    return "，".join(parts) + "。"
