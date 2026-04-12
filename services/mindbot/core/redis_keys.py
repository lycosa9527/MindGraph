"""Centralized Redis key prefixes and TTLs for MindBot (Dify conversation + dedup)."""

from __future__ import annotations

CONV_KEY_PREFIX = "mindbot:dify_conv:"
MSG_DEDUP_PREFIX = "mindbot:msg:"
MSG_DEDUP_TTL = 3600
CONV_KEY_TTL_SECONDS = 86400 * 30
TURN_COUNT_PREFIX = "mindbot:edu_turn:"
TURN_COUNT_TTL_SECONDS = CONV_KEY_TTL_SECONDS
