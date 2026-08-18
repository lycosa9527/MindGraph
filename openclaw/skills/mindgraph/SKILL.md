---
name: mindgraph
description: Author MindGraph semantic diagram specs (or generate from a topic), save, and render PNG. Prefer agent-authored spec when you already have content; use generate_graph only for topic-only requests.
metadata: {"openclaw": {"emoji": "🧠", "requires": {"env": ["MINDGRAPH_BASE_URL", "MINDGRAPH_ACCOUNT", "MINDGRAPH_TOKEN"]}}}
---

# MindGraph

Use env `MINDGRAPH_BASE_URL`, `MINDGRAPH_ACCOUNT` (phone), `MINDGRAPH_TOKEN` (`mgat_…`). Never echo token/account. Human setup: see `README.md`.

## Which flow

Two ways (both end in **save → PNG**):

| Way | When | Pipeline |
|-----|------|----------|
| **1. Agent diagram spec** | You already organized the content | Intent → type → author semantic `spec` → `POST /api/diagrams` → `GET …/png`. **No** `generate_graph`. |
| **2. Native prompt** | Topic / short instruction only | `POST /api/generate_graph` → if `success` + `spec` → create with that `diagram_type` + `spec` → PNG |

Label fixes on an existing diagram: `GET /api/diagrams/{id}` → `PATCH …/nodes` → PNG.

**Do not** invent canvas `{nodes, connections}` or mind-map `_layout`. Frontend lays out.

## Intent → `diagram_type`

If the user does not name a type, pick from intent. Ask once if two types are equally plausible.

| `diagram_type` | 中文名 | 思维意图 | User cues |
|----------------|--------|----------|-----------|
| `circle_map` | 圆圈图 | 联想 / 脑暴 | 联想、头脑风暴、围绕…想到什么 |
| `bubble_map` | 气泡图 | 描述特性 | 描述、特征、属性、特点 |
| `double_bubble_map` | 双气泡图 | 比较与对比 | 比较、对比、相同点、不同点、A和B |
| `tree_map` | 树形图 | 分类与归纳 | 分类、归纳、类别、分组 |
| `brace_map` | 括号图 | 整体与部分 | 组成、部分、结构、拆解 |
| `flow_map` | 流程图 | 顺序与步骤 | 步骤、流程、顺序、先…再… |
| `multi_flow_map` | 复流程图 | 因果分析 | 原因、结果、导致、因为、所以 |
| `bridge_map` | 桥形图 | 类比推理 | 类比、正如、好像、A之于B |
| `mind_map` | 思维导图 | 概念梳理 | 导图、分支；alias `mindmap` → `mind_map` |
| `concept_map` | 概念图 | 概念关系 | 概念之间的关系 / labeled links |

Topic only, no cue: omit `diagram_type` on `generate_graph` (auto-detect) or pick closest and state it briefly.

## Auth (every request)

- `Authorization: Bearer {MINDGRAPH_TOKEN}`
- `X-MG-Account: {MINDGRAPH_ACCOUNT}` (**required** with `mgat_`)
- `X-MG-Client: openclaw` (recommended)
- `X-Request-Id` (recommended on long PNG calls)

Use **current** env values every time. After user changes credentials, host may need restart/reload before new env applies.

## A. Agent-authored spec → render

### A1. Build `spec`

Match cookbook below. Set `title` from the topic; set `language` to the user’s language (`zh` / `en`).

### A2. Save

`POST {MINDGRAPH_BASE_URL}/api/diagrams`

```json
{
  "title": "Photosynthesis",
  "diagram_type": "mind_map",
  "spec": { },
  "language": "zh"
}
```

Response includes `id`. Server validates `spec`; on failure → **400** (see Spec errors).

### A3. PNG for the user

`GET {MINDGRAPH_BASE_URL}/api/diagrams/{id}/png`

→ `{ "url", "filename" }`. Pass **`url`** to the image tool (signed query; no Bearer on fetch). Long client timeout (Playwright; often >60s).

### Spec errors

- **422** — broken JSON (brackets/commas). Fix syntax; retry.
- **400** `detail.error === "invalid_diagram_spec"` — fix every string in `detail.issues`; retry save. Do **not** call `generate_graph` to dodge a bad spec.

```json
{
  "detail": {
    "error": "invalid_diagram_spec",
    "diagram_type": "bubble_map",
    "issues": ["Missing required field 'attributes' for bubble_map"]
  }
}
```

## Semantic spec cookbook

Required shapes only. Aliases accepted: `contexts`→`context`; `left_topic`/`right_topic`; `categories`→`children`; `topic`→`whole`/`title`/`event` where noted. Nodes need **`text` or `label`** (brace parts use **`name`**).

### `circle_map`

```json
{ "topic": "Photosynthesis", "context": ["sun", "water", "CO2", "chlorophyll"] }
```

### `bubble_map`

```json
{ "topic": "Lion", "attributes": ["fierce", "mane", "predator"] }
```

### `double_bubble_map`

```json
{
  "left": "Cat",
  "right": "Dog",
  "similarities": ["pets"],
  "left_differences": ["meows"],
  "right_differences": ["barks"]
}
```

### `tree_map`

```json
{
  "topic": "Animals",
  "children": [
    { "text": "Mammals", "children": [{ "text": "Dog", "children": [] }] }
  ]
}
```

### `brace_map`

```json
{
  "whole": "Plant",
  "parts": [{ "name": "Root", "subparts": [{ "name": "Hair" }] }]
}
```

### `flow_map`

```json
{
  "title": "Brew coffee",
  "steps": ["Grind", "Brew"],
  "substeps": [{ "step": "Grind", "substeps": ["Measure beans"] }]
}
```

(`substeps` optional.)

### `multi_flow_map`

```json
{ "event": "Rain", "causes": ["Clouds"], "effects": ["Wet ground"] }
```

### `bridge_map`

```json
{
  "relating_factor": "as",
  "analogies": [{ "left": "bird", "right": "plane" }]
}
```

### `mind_map`

```json
{
  "topic": "Central idea",
  "children": [
    {
      "label": "Branch",
      "text": "Branch",
      "children": [
        { "label": "Leaf", "text": "Leaf", "children": [] }
      ]
    }
  ]
}
```

### `concept_map`

```json
{
  "topic": "What is water?",
  "focus_question": "What is water?",
  "concepts": ["H2O"],
  "relationships": [{ "from": "What is water?", "to": "H2O", "label": "is" }]
}
```

(`concepts` / `relationships` may be `[]`.)

## B. Native prompt (fallback)

`POST {MINDGRAPH_BASE_URL}/api/generate_graph`

```json
{
  "prompt": "Photosynthesis",
  "diagram_type": "mind_map",
  "language": "zh",
  "llm": "qwen"
}
```

- `diagram_type` optional (auto-detect).
- Response: `success`, `spec`, `diagram_type`, optional `error`.

**Only continue when `success` is true and `spec` is present.** HTTP **200** + `"success": false` means stop — surface `error` (timeout/LLM). Do not save.

Then **A2 + A3** with the response **`diagram_type`** and **`spec`** unchanged (unless the user asked for edits).

## C. Patch existing

`GET {MINDGRAPH_BASE_URL}/api/diagrams/{id}` then:

```json
{ "action": "update", "updates": [{ "node_id": "<canvas-uuid>", "new_text": "New label" }] }
```

Or full replace `{ "spec": { } }` (same validator as create). Actions: `update` | `add` | `delete`. Then **A3**.

## Optional shortcuts

| Path | When |
|------|------|
| `POST /api/export_png` | Spec → PNG bytes (no library save); body `diagram_data` + `diagram_type` |
| `GET /api/diagrams` | List before editing |
| Web-content / inline recommendations / DingTalk one-shots | Prefer browser UI or product docs; not the default chat path |

Rate limits: PNG URL ~**20/min**; many generate/export ~**100/min**. On **429**, back off.

## Best practices

- Prefer way **1** when you have content; way **2** for topic-only.
- Match `language` to the user; use topic as `title`.
- On **400** `invalid_diagram_spec`, fix `issues` and retry; on **422**, fix JSON.
- After any mutation, fetch PNG (**A3**) before replying.
- Tokens last **90 days**. **403** may mean school tier lacks `api_token` / `chrome_extension`, or diagram library cap.
