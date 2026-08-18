# Mind-map node identity

Canvas `node.id` is the stable identity of a mind-map branch. Location is derived
from the tree, not encoded in the id.

This contract is shared by every agent on [`DiagramCommandBus`](diagram_edit_tool.md)
(Kitty, Zhihui, MindBot, classroom, Word add-in).

## Fields

| Field | Meaning | Example |
|---|---|---|
| `id` / `node_id` | Durable identity (UUID, same value as `data.mindMapUid`) | `3f2a…` |
| `path` | Current location only | `r/0/1` |
| `type` | `topic` vs `branch` | `branch` |
| `data.mindMapSide` | Stamped left/right | `right` |
| `data.mindMapDepth` | Stamped hop count from topic | `2` |

Topic stays `id: "topic"`.

`data.mindMapUid` equals `node.id` during the transition so old hydrate and
fingerprints still match. Do not treat `path` or outline `1.1.1` as a key.

## Agent rules

| Field | Agent may | Agent must not |
|---|---|---|
| `id` / `node_id` | Target, store, chain (`created_node_ids`) | Invent an id for a new node |
| `path` / outline `1.1.1` | Talk to the user (“右边第一个”) | Use as a durable key |
| `type` | Distinguish `topic` vs `branch` | Assume the id prefix encodes type |

Compact snapshot for every node-action prompt: `{id, text, type, path}`.
`id` is the UUID. `path` is the current location only.

`add_node` never invents an id. The canvas assigns the UUID and returns it in
`created_node_ids` so the next tool call (auto-complete, fill) can target the
new branch.

## Resolve order (FE + BE)

1. Exact `node.id` (UUID, or `"topic"`)
2. `data.mindMapUid`
3. Unique label
4. Leftover invented ids (`branch-r-1-0`, `branch_1`, …) **only** as aliases via `mindMapLegacyId` / migrate map — never as a live `node.id`

## Load migrate

Saved library specs, hub `live_spec`, and soft load
(`preferLaidOutMindMapNodes`) rewrite positional ids to the existing uid
(or a minted UUID), then rewrite connections, `_node_styles` keys, and
persisted classroom / Zhihui `focus_node_ids`.

## Verify

Delete and update postconditions target `node.id`. Update proves **this id’s**
text changed. Recycled `branch-*` addresses are never used as a verify key.

This is a different layer from account identity
([`identity_unification.md`](identity_unification.md)).
