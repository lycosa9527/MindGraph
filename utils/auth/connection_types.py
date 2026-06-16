"""Shared HTTP/WebSocket connection types for auth and geo middleware."""

from __future__ import annotations

from typing import Union

from fastapi import Request, WebSocket

HttpOrWebSocket = Union[Request, WebSocket]
