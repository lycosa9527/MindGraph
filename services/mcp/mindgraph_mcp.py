"""FastMCP server: prompt to diagram image via POST /api/generate_dingtalk."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from config.settings import config

logger = logging.getLogger(__name__)

_MCP_SINGLETON: dict[str, FastMCP] = {}


def _internal_base_url() -> str:
    """Base URL for loopback HTTP calls from MCP tool handlers into this app."""
    override = (os.environ.get("MCP_HTTP_INTERNAL_BASE_URL") or "").strip().rstrip("/")
    if override:
        return override
    return f"http://127.0.0.1:{config.port}"


def _auth_headers_from_context(ctx: Context) -> dict[str, str]:
    http_request = ctx.request_context.request
    if http_request is None:
        raise ValueError(
            "MCP tool requires Streamable HTTP with a Starlette request context; "
            "Authorization and X-MG-Account headers are missing."
        )
    auth = (http_request.headers.get("authorization") or "").strip()
    account = (http_request.headers.get("x-mg-account") or "").strip()
    if not auth.lower().startswith("bearer "):
        raise ValueError("Authorization header must be Bearer token (mgat_...).")
    if not account:
        raise ValueError("X-MG-Account header is required (account phone number).")
    return {
        "Authorization": auth,
        "X-MG-Account": account,
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }


def build_mindgraph_mcp() -> FastMCP:
    """
    Build the FastMCP app with Streamable HTTP settings suitable for mounting on FastAPI.

    DNS rebinding checks are disabled here; the outer FastAPI app and reverse proxy enforce host policy.
    """
    mcp = FastMCP(
        name="MindGraph",
        instructions=(
            "Generate a diagram image from a natural-language prompt using the MindGraph account "
            "associated with the request headers (Bearer mgat_ token and X-MG-Account). "
            "Returns markdown with an image URL, same as POST /api/generate_dingtalk."
        ),
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @mcp.tool()
    async def mindgraph_prompt_to_diagram_image(
        prompt: str,
        language: str = "zh",
        ctx: Optional[Context] = None,
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


def get_mindgraph_mcp() -> FastMCP:
    """Return a process-wide singleton FastMCP instance for mounting."""
    if "app" not in _MCP_SINGLETON:
        _MCP_SINGLETON["app"] = build_mindgraph_mcp()
    return _MCP_SINGLETON["app"]
