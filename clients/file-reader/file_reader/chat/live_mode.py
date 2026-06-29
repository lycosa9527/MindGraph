"""Shared live DB session typing for WeChat, DingTalk, and WeCom."""

from __future__ import annotations

from typing import Union

from file_reader.dingtalk.db_reader import DingTalkSessionPreview
from file_reader.wechat.db_reader import WeChatSessionPreview
from file_reader.wecom.db_reader import WeComSessionPreview

LiveChatSession = Union[WeChatSessionPreview, DingTalkSessionPreview, WeComSessionPreview]
