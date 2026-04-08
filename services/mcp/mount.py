"""Mount MindGraph Streamable HTTP MCP on the FastAPI application."""

from fastapi import FastAPI


def mount_mindgraph_mcp(app: FastAPI) -> None:
    """
    Mount MCP Streamable HTTP at /api/mcp (single route / inside the sub-app).

    Lifespan: the Starlette sub-app runs StreamableHTTPSessionManager; FastAPI propagates
    mounted application lifespan in supported versions.
    """
    from services.mcp.mindgraph_mcp import get_mindgraph_mcp

    mcp = get_mindgraph_mcp()
    app.mount("/api/mcp", mcp.streamable_http_app())
