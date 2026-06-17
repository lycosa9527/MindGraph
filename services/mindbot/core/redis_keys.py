"""Centralized Redis key prefixes and TTLs for MindBot (Dify conversation + dedup).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

CONV_KEY_PREFIX = "mindbot:dify_conv:"
MSG_DEDUP_PREFIX = "mindbot:msg:"
MSG_DEDUP_TTL = 3600
CONV_KEY_TTL_SECONDS = 86400 * 30
TURN_COUNT_PREFIX = "mindbot:edu_turn:"
TURN_COUNT_TTL_SECONDS = CONV_KEY_TTL_SECONDS
SEND_TRACKER_PREFIX = "mindbot:send_track:"
SEND_TRACKER_TTL = 7200
