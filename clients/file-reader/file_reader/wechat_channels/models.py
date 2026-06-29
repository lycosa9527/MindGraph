"""Models for captured WeChat Channels videos."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapturedChannelVideo:
    """One Channels video discovered from page/network capture."""

    video_id: str
    title: str
    media_url: str
    decode_key: str = ""
    uploader: str = ""

    def asset_id(self) -> str:
        """Stable id for DetectedAsset rows."""
        if self.video_id:
            return f"wechat-channels:{self.video_id}"
        return f"wechat-channels:{hash(self.media_url) & 0xFFFFFFFF:08x}"
