"""
Client-abort boundary for the ASGI app Uvicorn calls.

``BaseHTTPMiddleware`` turns a client disconnect into
``RuntimeError("No response returned.")`` outside ``ExceptionMiddleware``.
The ``Exception`` handler can answer 204, but Starlette's
``ServerErrorMiddleware`` always re-raises after that. Uvicorn then logs
``Exception in ASGI application``. Swallow only that abort here, after the
handler has already answered.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import FastAPI
from starlette.requests import ClientDisconnect
from starlette.types import Receive, Scope, Send
from uvicorn.protocols.utils import ClientDisconnected

_NO_RESPONSE = "No response returned."


def is_client_abort(exc: BaseException) -> bool:
    """True when the caller closed the connection and there is no app fault."""
    if isinstance(exc, (ClientDisconnect, ClientDisconnected)):
        return True
    if isinstance(exc, RuntimeError):
        text = exc.args[0] if exc.args else ""
        return isinstance(text, str) and _NO_RESPONSE in text
    return False


class MindGraphFastAPI(FastAPI):
    """FastAPI app that does not report a client abort as an ASGI crash."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except (ClientDisconnect, ClientDisconnected, RuntimeError) as exc:
            if scope.get("type") == "http" and is_client_abort(exc):
                return
            raise
