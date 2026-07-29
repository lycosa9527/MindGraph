"""
Mount MindGraph Streamable HTTP MCP on the FastAPI application.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import FastAPI

from services.mcp.mindgraph_mcp import mindgraph_mcp_asgi_app


def mount_mindgraph_mcp(app: FastAPI) -> None:
    """
    Mount MCP Streamable HTTP at /api/mcp (single route / inside the sub-app).

    Lifespan: the Starlette sub-app runs StreamableHTTPSessionManager; FastAPI propagates
    mounted application lifespan in supported versions. mcp 2.x enters lifespan once at
    manager startup (shared across requests when stateless_http=True).
    """
    app.mount("/api/mcp", mindgraph_mcp_asgi_app())
