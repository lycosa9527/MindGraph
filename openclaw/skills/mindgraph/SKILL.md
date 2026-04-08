---
name: mindgraph
description: Create, edit, and get AI recommendations for MindGraph diagrams on a live SaaS account (mind maps, thinking maps, concept maps).
metadata: {"openclaw": {"emoji": "🧠", "requires": {"env": ["MINDGRAPH_BASE_URL", "MINDGRAPH_ACCOUNT", "MINDGRAPH_TOKEN"]}}}
---

# MindGraph

MindGraph is an AI-assisted diagram platform. Use this skill with the configured base URL, account number (phone), and API token.

## Authentication (every request)

Set headers on all HTTP calls:

- `Authorization: Bearer {MINDGRAPH_TOKEN}` — token starts with `mgat_`
- `X-MG-Account: {MINDGRAPH_ACCOUNT}` — same phone number as the MindGraph account (no spaces)

Never print or log the token or account in assistant-visible output.

**Use current env on every request.** Substitute `MINDGRAPH_BASE_URL`, `MINDGRAPH_ACCOUNT`, and `MINDGRAPH_TOKEN` from the skill environment each time you build a URL or headers. Do not reuse token or account values from earlier messages if the user said they updated credentials—use the latest configured values.

## Updating auth (works immediately on the server)

- **MindGraph API** checks the Bearer token and `X-MG-Account` on **every** request. There is no sync delay: after the user generates or regenerates a token in the app, that token is valid on the **next** HTTP call with matching headers. Regenerating revokes the previous token immediately.
- **OpenClaw / WorkBuddy host** may inject `env` only when the app starts or when the skill reloads. If the user changed `MINDGRAPH_*` in config but requests still behave like the old credentials, they should **save** the config and **restart** the client (or use the host’s reload/restart skill action if it has one). After the new env is loaded, requests use the new values immediately—no extra step on MindGraph’s side.

## Setup

1. Log into MindGraph in the browser.
2. Open **账户信息** → **API Token** → **生成 Token**.
3. Copy the token once; set `MINDGRAPH_TOKEN` and `MINDGRAPH_ACCOUNT` (phone) and `MINDGRAPH_BASE_URL` (default test deployment: `https://test.mindspringedu.com`; override for your own host) in OpenClaw skill env.
4. Tokens expire after 7 days; regenerate from the same UI.

## 1. Generate diagram spec

`POST {MINDGRAPH_BASE_URL}/api/generate_graph`

JSON body (example):

```json
{ "topic": "Photosynthesis", "diagram_type": "mindmap" }
```

`diagram_type` examples: `circle_map`, `bubble_map`, `mindmap`, `tree_map`, `concept_map`, `flow_map`, etc.

Response includes the generated **spec** (diagram JSON).

## 2. Save diagram

`POST {MINDGRAPH_BASE_URL}/api/diagrams`

```json
{
  "title": "My diagram",
  "diagram_type": "mindmap",
  "spec": { }
}
```

Use the `spec` from step 1. Response includes `id` (diagram id string).

## 3. Push diagram image to the user

After create or any edit:

`GET {MINDGRAPH_BASE_URL}/api/diagrams/{id}/png`

Response: `{ "url": "https://..." }`. Pass `url` to the **image** tool so the user sees the current canvas.

## 4. Read diagram (before edits)

`GET {MINDGRAPH_BASE_URL}/api/diagrams/{id}`

Use the returned `spec` and node IDs before patching.

## 5. Patch nodes (optional)

`PATCH {MINDGRAPH_BASE_URL}/api/diagrams/{id}/nodes`

Either full replace:

```json
{ "spec": { } }
```

Or structured updates:

```json
{ "action": "update", "updates": [{ "node_id": "branch_0", "new_text": "New label" }] }
```

Actions: `update`, `add`, `delete` (see API error messages for required fields). Then call step 3 again for a fresh image.

## 6. Inline recommendations

These routes live **without** the `/api` prefix (root of `MINDGRAPH_BASE_URL`):

- `POST {MINDGRAPH_BASE_URL}/thinking_mode/inline_recommendations/start`
- `POST {MINDGRAPH_BASE_URL}/thinking_mode/inline_recommendations/next_batch`
- `POST {MINDGRAPH_BASE_URL}/thinking_mode/inline_recommendations/cleanup`

**Response type:** `start` and `next_batch` return **`text/event-stream` (SSE)**, not a single JSON body. The stream emits `data: {...}` lines. Parse JSON after each `data:` prefix; handle events such as `recommendation_generated` (includes recommendation text) and `error`.

Request bodies must match the server schema (e.g. `session_id`, `diagram_type`, `stage`, `node_id`, `nodes`, `language`, `count` — see the app’s OpenAPI or `InlineRecommendationsStartRequest` / `InlineRecommendationsNextRequest`).

Workflow: `start` (SSE) → optional `next_batch` (SSE) for more items → `cleanup` (JSON) with `node_ids`. Present suggestions to the user; apply the chosen item via PATCH (step 5) and push image (step 3).

If the HTTP client cannot read SSE, inline recommendations may not be usable from that environment — prefer the browser UI for that flow.

## Best practices

- Always send **Authorization** + **X-MG-Account** on every call, using **current** `MINDGRAPH_*` env values (see **Authentication** and **Updating auth** above).
- After **any** mutation, fetch the PNG URL (step 3) before replying.
- Prefer reading the diagram (step 4) before PATCH when IDs are unknown.
- Warn the user before token expiry when relevant.
- If auth fails after the user updated env in WorkBuddy/OpenClaw, suggest saving config and restarting the host app so new variables are picked up; then retry.
