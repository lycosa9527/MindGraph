"""
Mount MindGraph Streamable HTTP MCP on the FastAPI application.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import FastAPI

from services.mcp.mindgraph_mcp import get_mindgraph_mcp


def mount_mindgraph_mcp(app: FastAPI) -> None:
    """
    Mount MCP Streamable HTTP at /api/mcp (single route / inside the sub-app).

    Lifespan: the Starlette sub-app runs StreamableHTTPSessionManager; FastAPI propagates
    mounted application lifespan in supported versions.
    """
    mcp = get_mindgraph_mcp()
    app.mount("/api/mcp", mcp.streamable_http_app())
