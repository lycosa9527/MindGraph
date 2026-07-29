"""MindGraph MCP (Model Context Protocol) integration.

Exposes Streamable HTTP MCP when FEATURE_MCP_HTTP is enabled, mounted at /api/mcp.
Tools forward the caller's Authorization and X-MG-Account headers to existing REST routes.

Import the server from ``services.mcp.mindgraph_mcp`` (or ``services.mcp.mount`` for FastAPI wiring).
Requires the ``mcp`` package (pinned to 2.x in requirements.txt).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
