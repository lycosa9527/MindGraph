# MindGraph MCP (Streamable HTTP)

MindGraph exposes a Model Context Protocol endpoint at `/api/mcp` for agent
clients (Cursor, Claude Desktop, OpenClaw-style tools) to generate diagram
images from natural-language prompts.

## Enable

```bash
FEATURE_MCP_HTTP=True
```

The route is always mounted; `feature_flag_gate` returns **404** when the flag
is false (hot on/off via admin env reload). Default is **False**.

Optional loopback-only override for the tool → REST hop:

```bash
# MCP_HTTP_INTERNAL_BASE_URL=http://127.0.0.1:9527
```

Non-loopback hosts are ignored.

## Auth

Every MCP HTTP method except `OPTIONS` requires:

| Header | Value |
|--------|--------|
| `Authorization` | `Bearer mgat_…` (user API token) |
| `X-MG-Account` | Account phone bound to that token |
| `X-MG-Client` | Optional; defaults to `mcp` |

Invalid or missing credentials → **401** / **403** before the MCP protocol
runs (`initialize` / `tools/list` are not open). CSRF is skipped for `/api/mcp`
(non-browser agents); transport auth is the control.

Mint a token in the web UI (Account → API Token) while logged in.

## Client config (Cursor)

Project `.cursor/mcp.json` or `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "mindgraph": {
      "url": "https://test.mindspringedu.com/api/mcp",
      "headers": {
        "Authorization": "Bearer ${env:MG_TOKEN}",
        "X-MG-Account": "${env:MG_ACCOUNT}"
      }
    }
  }
}
```

Set `MG_TOKEN` / `MG_ACCOUNT` in the environment. Prefer secrets over hardcoding.
Rotate any token that has been pasted into chat or logs.

## Tool surface

One tool today:

- `mindgraph_prompt_to_diagram_image(prompt, language="zh")` → markdown
  `![](url)`, same as `POST /api/generate_dingtalk`.

## Operations notes

- **Proxy timeouts:** tool wait is up to 180s. Set nginx/NPM
  `proxy_read_timeout` / `proxy_send_timeout` ≥ 180s for `/api` (300s matches
  MindMate). See [`production_security_deploy.md`](../architecture/production_security_deploy.md).
- **Multi-worker:** transport uses `stateless_http=True`. Each Uvicorn worker
  enters `session_manager.run()` in the host lifespan after mount.
- **Rate limit:** 100 requests / 60s per authenticated user (`mcp_http`).
- **IP audit:** MCP `TokenAudit` sees the real client IP. The tool’s loopback
  call to `/api/generate_dingtalk` appears as `127.0.0.1` by design (do not
  forward client `X-Forwarded-For` into that hop).
- **DNS rebinding:** disabled on the MCP sub-app; the reverse proxy must set
  `Host` and the app should use `ALLOWED_HOSTS` / `TRUSTED_PROXY_IPS` as usual.
