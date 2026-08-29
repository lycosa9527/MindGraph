---
name: mindgraph
description: Author a MindGraph semantic diagram spec, save it, and render PNG. You write the spec. MindGraph only stores and draws. Never call generate_graph or any prompt/LLM generate API.
metadata: {"openclaw": {"emoji": "🧠", "requires": {"env": ["MINDGRAPH_BASE_URL", "MINDGRAPH_ACCOUNT", "MINDGRAPH_TOKEN"]}}}
---

# MindGraph

Use env `MINDGRAPH_BASE_URL`, `MINDGRAPH_ACCOUNT` (phone), `MINDGRAPH_TOKEN` (`mgat_…`). Never echo token/account. Human setup: see `README.md`.

MindGraph is the **pen**. You are the **author**. Always build the semantic `spec` yourself — even if the user only gives a topic. Then save and render.

**Never** call `POST /api/generate_graph`, `/api/generate_graph/stream`, `/api/generate_dingtalk`, `/api/web_content_mindmap_png`, or any other prompt-to-diagram route.

**Do not** invent canvas `{nodes, connections}` or mind-map `_layout`. Frontend lays out.

## Flow

Intent → `diagram_type` → author `spec` (cookbook) → `POST /api/diagrams` → `GET …/png`.

Edit an existing diagram: `GET /api/diagrams/{id}` → `PATCH …/nodes` → PNG.

## Pick `diagram_type`

You must choose the type. MindGraph will not guess.

**Order:**

1. User **names a type** (中文名 or English) → use that. The *topic* may mention another type — ignore that.  
   「生成一个关于思维导图的气泡图」→ `bubble_map` (topic = 思维导图).
2. Else match **thinking intent** (table + lookalikes). Prefer the **most specific** type.
3. Topic only / “做个图” / unclear → `mind_map`. Say the type in one short line.
4. Two types equally good → ask **once**, then draw.

Named-type aliases: `mindmap` → `mind_map`; 类比图 → `bridge_map`; 复流程图 / 多重流程图 → `multi_flow_map`.

| `diagram_type` | 中文名 | Use when | Not when | Cues |
|----------------|--------|----------|----------|------|
| `circle_map` | 圆圈图 | Define a thing **in context**: what comes to mind, examples, observations around one topic | Adjectives only (use bubble); nested branches (use mind/tree) | 定义、联想、围绕…想到什么、上下文、例子 |
| `bubble_map` | 气泡图 | **Describe one** thing with qualities (adjectives / attributes) | Two things to compare (double bubble); context words that are not traits | 描述、特征、属性、特点、品质 |
| `double_bubble_map` | 双气泡图 | **Compare two** named things: same + different | Analogy “A is to B as C is to D” (bridge); more than two items to classify (tree) | 比较、对比、相同点、不同点、A和B / vs |
| `tree_map` | 树形图 | **Classify kinds**: categories and sub-kinds (taxonomy) | Physical parts of one object (brace); free brainstorm (mind) | 分类、归纳、类别、分组、种类 |
| `brace_map` | 括号图 | **Whole → parts** of one object (anatomy / composition) | Kinds/categories (tree); steps in time (flow) | 组成、部分、结构、拆解、构件 |
| `flow_map` | 流程图 | **Order in time**: steps, how-to, process | Why it happened (multi-flow); parts of a thing (brace) | 步骤、流程、顺序、先…再…、如何 |
| `multi_flow_map` | 复流程图 | **Cause ↔ effect** around one event (many reasons / many results) | Ordered how-to (flow); two-item compare (double bubble) | 原因、结果、导致、因为、所以、为何 |
| `bridge_map` | 桥形图 | **Analogy pairs** that share one relation (A:B as C:D) | Side-by-side compare of two topics (double bubble) | 类比、正如、好像、之于、像…一样 |
| `mind_map` | 思维导图 | **Organize / diverge** from a center: themes and sub-ideas | Labeled “A —rel→ B” network (concept); one-ring context (circle) | 导图、分支、梳理、发散 |
| `concept_map` | 概念图 | **Network of concepts** with **labeled links** (propositions) | Simple star of branches (mind); adjective list (bubble) | 概念关系、是、导致、属于、连接词 |

### Lookalikes (do not mix)

- **Circle vs bubble** — circle = context / examples around a topic. Bubble = traits of that topic (`fierce`, `mane`). “狮子有什么特点” → bubble. “提到光合作用你会想到什么” → circle.
- **Tree vs brace** — tree = *kinds* (动物 → 哺乳类 → 狗). Brace = *parts* (植物 → 根 → 根毛). “电脑有哪些组成部分” → brace. “动物怎么分类” → tree.
- **Flow vs multi-flow** — flow = sequence (煮咖啡：研磨 → 冲泡). Multi-flow = why/what followed (酒精灯爆炸：原因… / 结果…). “怎么做” → flow. “为什么 / 造成什么” → multi-flow.
- **Double bubble vs bridge** — double bubble = Cat vs Dog (same + different). Bridge = bird:plane as fish:submarine (same *relation*). “比较A和B” → double bubble. “A之于B正如…” → bridge.
- **Mind vs concept** — mind = branches from a center, no required link words. Concept = many concepts + `relationships` with labels (`is`, `causes`). “梳理知识点” → mind. “概念之间怎么连” → concept.
- **Mind vs circle** — circle is a **flat** ring of associations. Mind has **nested** children. Deep outline → mind.

### Worked picks

| User says | Type | Why |
|-----------|------|-----|
| 比较猫和狗 | `double_bubble_map` | two things, same/different |
| 植物由哪些部分组成 | `brace_map` | one whole, parts |
| 动物分类 | `tree_map` | kinds, not parts |
| 光合作用的步骤 | `flow_map` | order |
| 为什么下雨，会怎样 | `multi_flow_map` | causes + effects |
| 鸟之于飞机，正如… | `bridge_map` | analogy pairs |
| 狮子有什么特点 | `bubble_map` | attributes |
| 提到春天你会想到什么 | `circle_map` | context ring |
| 梳理人工智能 | `mind_map` | default organize |
| 水、H₂O、蒸发之间的关系 | `concept_map` | labeled links |

## Auth (every request)

- `Authorization: Bearer {MINDGRAPH_TOKEN}`
- `X-MG-Account: {MINDGRAPH_ACCOUNT}` (**required** with `mgat_`)
- `X-MG-Client: openclaw` (recommended)
- `X-Request-Id` (recommended on long PNG calls)

Use **current** env values every time. After user changes credentials, host may need restart/reload before new env applies.

### Change account / token (skill-creator)

When the user says edit this skill / 改账号 / 改 token / 换环境:

1. **Never** write phone or `mgat_…` into `SKILL.md`. Auth is **env only**.
2. Set these three keys (keep any key the user did not change):
   - `MINDGRAPH_BASE_URL` — HTTPS origin, no trailing slash
   - `MINDGRAPH_ACCOUNT` — phone / login
   - `MINDGRAPH_TOKEN` — `mgat_…` (90 days)
3. Write them here, first match wins:
   1. Host skill env: `skills.entries.mindgraph.env` in WorkBuddy / OpenClaw config (e.g. `%USERPROFILE%\.openclaw\openclaw.json`, WorkBuddy 技能设置 JSON).
   2. Else the **installed** skill `demo.json` env block (local machine only).
   3. Else tell the user the three values must be pasted in 技能 / 环境变量. Do not invent a new file in `SKILL.md`.
4. Confirm with `GET {MINDGRAPH_BASE_URL}/api/diagrams?page=1&page_size=1` (same auth headers). Report **HTTP status only**. Never echo the token in chat or in files you show the user.
5. Tell the user to **save + restart** WorkBuddy/OpenClaw (or reload skills) so the new env is loaded.

Do not publish or commit a `demo.json` that contains a real token.

### HTTP errors (not spec)

Do **not** rewrite the spec or call any generate API for these. Never echo the token.

| Code | Meaning | What to do |
|------|---------|------------|
| **401** | Token missing/wrong, or no `X-MG-Account` | Ask the user to check `MINDGRAPH_TOKEN` + `MINDGRAPH_ACCOUNT`, save env, restart WorkBuddy/OpenClaw. |
| **403** | School tier lacks `api_token` / `chrome_extension`, or diagram library cap | Tell the user; do not retry. |
| **429** | Rate limit (PNG ~20/min; export ~100/min) | Wait, then retry the **same** call once. |
| **500** on PNG | Draw failed | Retry PNG **once**. If it fails again, tell the user. Keep the saved spec. |

## A. Author spec → save → PNG

### A1. Build `spec`

Match cookbook below. Set `title` from the topic; set `language` to the user’s language (`zh` / `en`). If the user only gave a topic, you still invent a complete, valid spec.

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
- **400** `detail.error === "invalid_diagram_spec"` — fix every string in `detail.issues`; retry save. Do **not** call any generate API.

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

## B. Patch existing

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

## Best practices

- You write the spec. MindGraph only validates, saves, and draws.
- Match `language` to the user; use topic as `title`.
- On **400** `invalid_diagram_spec`, fix `issues` and retry; on **422**, fix JSON.
- After any mutation, fetch PNG (**A3**) before replying.
- Tokens last **90 days**. Auth / rate / PNG failures: see **HTTP errors**.
