"""
Host-app lifespan hook for MindGraph Streamable HTTP MCP.

Mounted sub-app lifespans do not run under FastAPI/Starlette, so the MCP
``StreamableHTTPSessionManager`` must be started from the parent lifespan via
``session_manager.run()``. Without this, every MCP request fails with:
``RuntimeError: Task group is not initialized. Make sure to use run()``.

Product on/off is owned by ``feature_flag_gate`` (FEATURE_MCP_HTTP), not this hook.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from services.mcp.mindgraph_mcp import get_mindgraph_mcp
from services.mcp.mount_state import is_mindgraph_mcp_mounted

logger = logging.getLogger(__name__)


@asynccontextmanager
async def mindgraph_mcp_session_run() -> AsyncIterator[None]:
    """
    Enter MCP ``session_manager.run()`` when Streamable HTTP MCP was mounted.

    ``session_manager`` exists only after ``streamable_http_app()`` (called from
    ``mount_mindgraph_mcp``). If mount failed or the manager is missing, this is
    a no-op so host startup is unchanged.
    """
    if not is_mindgraph_mcp_mounted():
        yield
        return

    server = get_mindgraph_mcp()
    manager = getattr(server, "session_manager", None)
    if manager is None:
        logger.warning("[MCP] MCP was marked mounted but session_manager is missing; was streamable_http_app() called?")
        yield
        return

    async with manager.run():
        logger.info("[MCP] Streamable HTTP session manager started")
        yield
