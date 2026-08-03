"""MindGraph MCP (Model Context Protocol) integration.

Exposes Streamable HTTP MCP at /api/mcp (always mounted; gated by FEATURE_MCP_HTTP).
Transport requires Bearer mgat_ + X-MG-Account. Tools forward those headers to REST.

Import the server from ``services.mcp.mindgraph_mcp`` (or ``services.mcp.mount`` for FastAPI wiring).
Host lifespan must enter ``mindgraph_mcp_session_run`` (see ``session_lifespan``).
Requires the ``mcp`` package (pinned to 2.x in requirements.txt).
See ``docs/operations/mcp_http.md``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
