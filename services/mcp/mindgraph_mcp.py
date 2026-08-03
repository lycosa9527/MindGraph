"""
MCPServer: prompt to diagram image via POST /api/generate_dingtalk.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Mapping
from urllib.parse import urlparse

import httpx
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from config.settings import config
from utils.auth.mg_client import MG_CLIENT_HEADER

logger = logging.getLogger(__name__)

_MCP_SINGLETON: dict[str, MCPServer] = {}

_TRANSPORT_SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_DEFAULT_MG_CLIENT = "mcp"


def _default_internal_base_url() -> str:
    """Default loopback base URL for MCP tool → REST calls."""
    return f"http://127.0.0.1:{config.port}"


def _internal_base_url() -> str:
    """
    Base URL for loopback HTTP calls from MCP tool handlers into this app.

    ``MCP_HTTP_INTERNAL_BASE_URL`` may override the default only when the host is
    loopback; non-loopback overrides are ignored (SSRF / misconfig guard).
    """
    override = (os.environ.get("MCP_HTTP_INTERNAL_BASE_URL") or "").strip().rstrip("/")
    if not override:
        return _default_internal_base_url()

    parsed = urlparse(override)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in _LOOPBACK_HOSTS:
        logger.warning(
            "[MCP] Ignoring non-loopback MCP_HTTP_INTERNAL_BASE_URL=%r; using %s",
            override,
            _default_internal_base_url(),
        )
        return _default_internal_base_url()
    return override


def _header_value(headers: Mapping[str, str], name: str) -> str:
    """Read a header by name (case-insensitive)."""
    direct = headers.get(name)
    if direct is not None:
        return direct.strip()
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value.strip()
    return ""


def _auth_headers_from_context(ctx: Context) -> dict[str, str]:
    """
    Auth headers from the Streamable HTTP request (Bearer mgat_ + X-MG-Account).

    Does not forward X-Forwarded-For / X-Real-IP (loopback is often a trusted
    proxy peer; client-supplied XFF would be spoofable).
    """
    try:
        incoming = ctx.headers
    except ValueError as exc:
        raise ValueError(
            "MCP tool requires Streamable HTTP with a Starlette request context; "
            "Authorization and X-MG-Account headers are missing."
        ) from exc
    if incoming is None:
        raise ValueError(
            "MCP tool requires Streamable HTTP with a Starlette request context; "
            "Authorization and X-MG-Account headers are missing."
        )
    auth = _header_value(incoming, "authorization")
    account = _header_value(incoming, "x-mg-account")
    if not auth.lower().startswith("bearer "):
        raise ValueError("Authorization header must be Bearer token (mgat_...).")
    token = auth[7:].strip()
    if not token.startswith("mgat_"):
        raise ValueError("Authorization header must be Bearer token (mgat_...).")
    if not account:
        raise ValueError("X-MG-Account header is required (account phone number).")

    mg_client = _header_value(incoming, MG_CLIENT_HEADER) or _DEFAULT_MG_CLIENT
    request_id = _header_value(incoming, "x-request-id") or str(uuid.uuid4())
    return {
        "Authorization": f"Bearer {token}",
        "X-MG-Account": account,
        MG_CLIENT_HEADER: mg_client,
        "X-Request-Id": request_id,
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }


def build_mindgraph_mcp() -> MCPServer:
    """
    Build the MCPServer with tools only.

    Transport settings (JSON response, stateless HTTP, path, DNS rebinding) are
    applied in ``mindgraph_mcp_asgi_app`` — mcp 2.x moved them off the constructor.
    """
    mcp = MCPServer(
        name="MindGraph",
        instructions=(
            "Generate a diagram image from a natural-language prompt using the MindGraph account "
            "associated with the request headers (Bearer mgat_ token and X-MG-Account). "
            "Returns markdown with an image URL, same as POST /api/generate_dingtalk."
        ),
    )

    @mcp.tool()
    async def mindgraph_prompt_to_diagram_image(
        prompt: str,
        language: str = "zh",
        ctx: Context | None = None,
    ) -> str:
        """
        Turn a teaching or topic prompt into a diagram PNG and return markdown ![](url).

        Authentication: same as the REST API — Bearer mgat_ token and X-MG-Account on the MCP HTTP request.
        """
        if ctx is None:
            return "Error: MCP context is required."
        try:
            headers = _auth_headers_from_context(ctx)
        except ValueError as exc:
            return f"Error: {exc}"

        body = {"prompt": prompt.strip(), "language": language}
        if not body["prompt"]:
            return "Error: prompt must not be empty."

        url = f"{_internal_base_url()}/api/generate_dingtalk"
        timeout = httpx.Timeout(180.0, connect=30.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("[MCP] generate_dingtalk request failed: %s", exc)
            return f"Error: request to MindGraph failed: {exc}"

        if response.status_code >= 400:
            text = response.text[:2000]
            return f"HTTP {response.status_code}: {text}"

        return response.text

    return mcp


def get_mindgraph_mcp() -> MCPServer:
    """Return a process-wide singleton MCPServer instance for mounting."""
    if "app" not in _MCP_SINGLETON:
        _MCP_SINGLETON["app"] = build_mindgraph_mcp()
    return _MCP_SINGLETON["app"]


def mindgraph_mcp_asgi_app() -> Starlette:
    """
    Streamable HTTP ASGI app for mounting at ``/api/mcp``.

    Path is ``/`` inside the mount so the public endpoint stays ``/api/mcp``.
    DNS rebinding checks are disabled here; the outer FastAPI app and reverse
    proxy enforce host policy.
    """
    return get_mindgraph_mcp().streamable_http_app(
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        transport_security=_TRANSPORT_SECURITY,
    )
