"""
Mount MindGraph Streamable HTTP MCP on the FastAPI application.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

from services.mcp.auth_middleware import McpMgatAuthMiddleware
from services.mcp.mindgraph_mcp import mindgraph_mcp_asgi_app
from services.mcp.mount_state import mark_mindgraph_mcp_mounted

logger = logging.getLogger(__name__)


class EnsureMcpTrailingSlashMiddleware:
    """
    Rewrite bare ``/api/mcp`` to ``/api/mcp/`` before routing.

    Starlette ``Mount("/api/mcp", ...)`` only dispatches paths under the mount
    with a trailing slash; POST to ``/api/mcp`` otherwise becomes 405 (redirect
    route is GET/HEAD only).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/api/mcp":
            scope = dict(scope)
            scope["path"] = "/api/mcp/"
            if "raw_path" in scope:
                scope["raw_path"] = b"/api/mcp/"
        await self.app(scope, receive, send)


def mount_mindgraph_mcp(app: FastAPI) -> None:
    """
    Mount MCP Streamable HTTP at /api/mcp (single route / inside the sub-app).

    Lifespan: mounted Starlette sub-apps do not run their own lifespan. The host
    FastAPI lifespan must enter ``session_manager.run()`` via
    ``mindgraph_mcp_session_run`` in ``services.mcp.session_lifespan``.
    Call ``streamable_http_app()`` here first so ``session_manager`` exists
    before that host lifespan hook runs.

    Product on/off is enforced by ``feature_flag_gate`` (FEATURE_MCP_HTTP).
    """
    app.add_middleware(EnsureMcpTrailingSlashMiddleware)
    app.mount("/api/mcp", McpMgatAuthMiddleware(mindgraph_mcp_asgi_app()))
    mark_mindgraph_mcp_mounted()
    logger.info("[MCP] Streamable HTTP mounted at /api/mcp (mgat_ auth required)")
