# Thinking Map node identity

The eight Thinking Maps use the same resolve contract as
[mind-map node identity](mindmap_node_identity.md):

1. Exact `node.id` (UUID or reserved root)
2. `data.*MapUid`
3. Unique label (exactly one text match)
4. Leftover invented ids (`context-0`, `context_0`, `flow-step-N`, …) **only** as aliases

Reserved roots stay fixed: `topic`, `outer-boundary`, `left-topic` / `right-topic`,
`tree-topic`, `brace-whole`, `flow-topic`, `event`, `dimension-label`.

`brace-0-0` rewrites to `brace-whole`. Kitty never invents `context_0`-style live ids.
The canvas assigns UUIDs; leftover prefixes live in `data.*LegacyId`.
