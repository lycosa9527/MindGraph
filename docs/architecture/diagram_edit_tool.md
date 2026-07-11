# Diagram Edit Tool

Agent-driven structural diagram edits go through one verified tool surface. **`applied` means the owning canvas proved the effect** — not “WebSocket sent” and not “LLM said so.”

## Package

`services/diagram_edit/`

| Module | Role |
|--------|------|
| `schema.py` | OpenAI-compatible tool defs (`diagram.add_node`, …) |
| `types.py` | `DiagramEditCommand`, `ExpectedEffect`, `ToolResult`, `ErrorCode` |
| `executor.py` | Authz → dispatch → await verified ack → revision |
| `pending.py` | `mutation_id` → `asyncio.Future`; timeout; idempotency cache |
| `verify.py` | Pure postconditions on `{nodes, connections}` |
| `effects.py` | Build `ExpectedEffect` from command + before snapshot |
| `registry.py` | Tool name → handler |
| `handlers/mindmap.py` | v1 mindmap dispatch (strangler over Kitty `diagram_execute`) |
| `transport/` | `CanvasTransport` protocol + `KittyWsTransport` (decouples executor from `voice_sessions`) |

## DiagramCommandBus (`services/agent_hub/diagram_spine/`)

Single front door for agent diagram mutations:

| Module | Role |
|--------|------|
| `types.py` | `DiagramCommandRequest`, `DiagramCommandResult` |
| `policy.py` | Scope access, revision, write-lock, owner checks (Kitty impl) |
| `bus.py` | `DiagramCommandBus.apply()` → policy → `execute_diagram_edit` |
| `origins.py` | `DiagramCommandOrigin`, `register_channel_adapter()` |

Kitty routes verified mindmap edits through `services/kitty/adapters/diagram_command.py` → Bus.
Legacy non-verified voice diagram intents use the same Bus with `verify_required=false`.

Frontend apply path: Kitty WS `diagram_update` emits `kitty:diagram_mutation_requested`;
`registerKittyDiagramMutationBus` owns Pinia apply + Hub persist (inbound does not mutate Pinia directly).
Owning tab skips legacy SSE fanout without `mutation_id` (`ownsKittySession`); observers recover via Hub `live_context`.

Kitty voice I/O (text-first): Fun-ASR realtime mic + CosyVoice realtime TTS on the shared MaaS
inference WebSocket (`build_dashscope_inference_ws_url`). Omni duplex is not used for Kitty commands.

## v1 scope

- Diagram type: `mindmap` / `mind_map`
- Tools: `diagram.update_center`, `diagram.add_node`, `diagram.update_node`, `diagram.delete_node`
- Kitty one-sentence **edit** phase adapter (forced structural parse; no `action:none` → chat)
- FE verify + `diagram_mutation_ack` + executor await (default **3s**)
- Write lock vs LLM `generate_graph`
- Canonical mindmap `loadFromSpec` when `spec.nodes[]` present

## Error codes

`not_parsed` | `unsupported_tool` | `unsupported_diagram_type` | `no_owner` | `stale_revision` | `apply_noop` | `verify_failed` | `ack_timeout` | `compensate_failed` | `access_denied` | `busy_llm_generating` | `hub_persist_failed`

## Command envelope

```json
{
  "tool": "diagram.add_node",
  "args": { "text": "DIY", "parent_ref": null, "side": "right" },
  "scope": "<diagram_scope>",
  "diagram_type": "mindmap",
  "expected_revision": 12,
  "idempotency_key": "...",
  "source_agent": "kitty"
}
```

## Result envelope

```json
{
  "status": "applied",
  "revision": 13,
  "mutation_id": "...",
  "applied_ops": [{ "op": "add_branch", "text": "DIY" }],
  "verification": { "ok": true, "checks": ["node_exists", "text_matches", "parent_edge_exists"] },
  "error_code": null
}
```

## Wire protocol

Outbound `diagram_update` (Kitty WS) includes:

- `mutation_id`
- `expected_effect`
- `before_fingerprint`

Inbound `diagram_mutation_ack` (combined — verify + hub persist):

```json
{
  "type": "diagram_mutation_ack",
  "mutation_id": "...",
  "verified": true,
  "hub_persist_ok": true,
  "hub_revision": 13,
  "revision": 13,
  "evidence": { "nodes": [...], "connections": [...] }
}
```

Server `applied` requires `hub_persist_ok: true` when `verify_required=true`. Hub save is **client-driven** (`context_update` → `context_mutation_ack`) — not server `children[]` guess.

**Owning client rule:** Only the tab with the active Kitty WebSocket applies, verifies, persists to Hub, and acks. Desktop SSE observers skip updates that carry `mutation_id`; they recover via `live_context` poll after Hub persist (`kitty:hub_diagram_persisted` without `source: owning_tab`). The owning tab emits `source: owning_tab` and **must not** reload Pinia from `live_context` (Pinia is already SoT). Hub `diagram_data` includes canonical `nodes`/`connections` from Pinia; recovery prefers those over flat `children[]`.

## Verification flow

1. Executor builds `ExpectedEffect` + `before_fingerprint`.
2. Canvas applies via `diagramEditApply` (Pinia `mindMapOps`).
3. FE `diagramEditVerify` runs postconditions.
4. On verify ok: `diagramEditHubPersist` sends Pinia snapshot via `context_update`, awaits `context_mutation_ack`.
5. On verify or Hub fail: compensate by reloading `before_fingerprint`; ack `verified: false` / `hub_persist_ok: false`.
6. Combined `diagram_mutation_ack` sent only after verify + Hub ack.
7. Executor awaits ack; BE `verify.py` re-checks ack `evidence`.

### Mindmap postconditions (v1)

| Tool | Must prove |
|------|------------|
| `add_node` (branch) | New node; text matches (trim+NFKC); parent `topic`; edge `topic→node`; \|nodes\| +1; one `topic` |
| `add_node` (child) | New node under branch; parent edge; \|nodes\| +1 |
| `update_node` | Target exists; text matches; node count unchanged |
| `update_center` | `topic` text matches; exactly one `topic` |
| `delete_node` | Target absent; no dangling edges; tree rooted at `topic` |

## Write lock

Context field `diagram_write_lock: { holder: "llm" | "tool" | null }`. Executor rejects with `busy_llm_generating` while `holder === "llm"`. `syncDiagramStoreFromVoiceContext` is blocked while locked.

## Kitty adapter

- Client sends `one_sentence_phase: "edit"` in `context_update`.
- Edit NL: `parse_one_sentence_edit_intent` → **NodeActionAgent** (`node_action_agent.py`) with
  `build_node_action_tools()` from `node_action_library.py` (structural `diagram.*` plus
  `auto_complete_branch`, `auto_complete`, `clarify_options`). Regex heuristics in
  `one_sentence_edit_heuristics.py` run only on LLM timeout or empty tool result.
- Agent reads full diagram JSON snapshot (nodes, ids, nested children) from session
  context — ground truth for matching labels and stable ``node_id`` targets.
- `command_router`: mindmap edit → `apply_kitty_legacy_diagram_command` (Bus); `action:none` → `FAILED`,
  never conversational; `clarify_options` → numbered chat ack + optional pending pick.
- Verified path: no `try_sync_voice_diagram_to_hub` while `mutation_id` extras are stashed —
  Hub revision bumps only after client `context_update` (Pinia SoT). Legacy voice still syncs.
- FE hub-persist wait is 3s; BE `wait_for_ack` default is **8s** so the client can finish Hub
  persist and still ack. Client-reported failures (`verify_failed`, `hub_persist_failed`, …)
  surface toast+chat on FE; BE skips a duplicate generic `execute_failed` text_chunk for those codes.

## Idempotency

Same `idempotency_key` returns cached `ToolResult`; must not apply a second mutation.

## P2

Non-mindmap `ExpectedEffect` tables and optional `POST /api/diagram_edit/execute` are out of v1.
One-sentence **verified** edit is mindmap-only by design (`_should_use_verified_diagram_edit`);
other diagram types still use the legacy Bus path (`verify_required=false`).
