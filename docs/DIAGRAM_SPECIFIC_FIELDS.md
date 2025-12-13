# Diagram-Specific Fields for Command Processing

This document comprehensively lists all diagram-specific fields and node types used in voice agent command processing logic for all 10 main diagram types.

## Overview

The voice agent processes commands differently based on diagram type. Some diagrams use specialized fields instead of the generic `target` or `new_text` fields. Some diagrams have hierarchical node structures requiring multiple indices (e.g., `step_index` + `substep_index` for flow maps).

---

## Complete Node Type Reference

### 1. **Circle Map** (`circle_map`)
- **Center Field**: `topic` (via `target` → `new_text`)
- **Node Type**: `context` (flat array)
- **Structure**: `{topic: "...", context: ["context1", "context2", ...]}`
- **Node Terminology**: "context 1", "context 2", "上下文1", "上下文2"

### 2. **Bubble Map** (`bubble_map`)
- **Center Field**: `topic` (via `target` → `new_text`)
- **Node Type**: `attributes` (flat array)
- **Structure**: `{topic: "...", attributes: ["attr1", "attr2", ...]}`
- **Node Terminology**: "attribute 1", "attribute 2", "属性1", "属性2"

### 3. **Double Bubble Map** (`double_bubble_map`)
- **Center Fields**: `left`, `right` (both required)
- **Node Types**: `similarities`, `left_differences`, `right_differences` (categorized arrays)
- **Structure**: `{left: "...", right: "...", similarities: [...], left_differences: [...], right_differences: [...]}`
- **Node Terminology**: "similarity", "left difference", "right difference", "共同点", "左边不同点", "右边不同点"

### 4. **Tree Map** (`tree_map`)
- **Center Field**: `topic` (via `target` → `new_text`)
- **Node Types**: `children` (hierarchical: categories with items)
- **Structure**: `{topic: "...", children: [{text: "Category", children: [{text: "Item", children: []}]}]}`
- **Node Terminology**: "category 1", "item 1", "类别1", "项目1"
- **Hierarchical Indices**: `category_index` (for categories), `item_index` (for items within categories)

### 5. **Flow Map** (`flow_map`)
- **Center Field**: `title`
- **Node Types**: `steps` (main steps, flat array) + `substeps` (sub-steps, hierarchical under steps)
- **Structure**: `{title: "...", steps: ["Step1", "Step2"], substeps: [{step: "Step1", substeps: ["Substep1.1", "Substep1.2"]}]}`
- **Node Terminology**: "step 1", "substep 1.1", "步骤1", "子步骤1.1"
- **Hierarchical Indices**: `step_index` (for steps), `substep_index` (for substeps within a step)

### 6. **Multi-Flow Map** (`multi_flow_map`)
- **Center Field**: `event`
- **Node Types**: `causes`, `effects` (categorized arrays)
- **Structure**: `{event: "...", causes: [...], effects: [...]}`
- **Node Terminology**: "cause 1", "effect 1", "原因1", "结果1"

### 7. **Brace Map** (`brace_map`)
- **Center Field**: `whole`
- **Node Types**: `parts` (hierarchical: parts with subparts)
- **Structure**: `{whole: "...", parts: [{name: "Part", subparts: [{name: "Subpart"}]}]}`
- **Node Terminology**: "part 1", "subpart 1.1", "部分1", "子部分1.1"
- **Hierarchical Indices**: `part_index` (for parts), `subpart_index` (for subparts within a part)

### 8. **Bridge Map** (`bridge_map`)
- **Center Field**: `dimension`
- **Node Type**: `analogies` (pairs with left/right)
- **Structure**: `{dimension: "...", analogies: [{left: "...", right: "..."}]}` or `{dimension: "...", analogies: ["left : right"]}`
- **Node Terminology**: "analogy 1", "pair 1", "类比1", "第一对"
- **Special Fields**: `left`, `right` (both required for analogies)

### 9. **Mindmap** (`mindmap`)
- **Center Field**: `topic` (via `target` → `new_text`)
- **Node Types**: `branches` (hierarchical: branches with children)
- **Structure**: `{topic: "...", children: [{id: "branch_0", label: "Branch", children: [{id: "sub_0_0", label: "Sub-branch"}]}]}`
- **Node Terminology**: "branch 1", "child 1.1", "分支1", "子项1.1"
- **Hierarchical Indices**: `branch_index` (for branches), `child_index` (for children within a branch)

### 10. **Concept Map** (`concept_map`)
- **Center Field**: `topic` (via `target` → `new_text`)
- **Node Types**: `concepts` (flat array) + `relationships` (edges between concepts)
- **Structure**: `{topic: "...", concepts: ["Concept1", "Concept2"], relationships: [{from: "...", to: "...", label: "..."}]}`
- **Node Terminology**: "concept 1", "concept 2", "概念1", "概念2"
- **Special Fields**: `from`, `to`, `label` (for relationships)

---

## Update Center (`update_center`) Fields

### 1. **Double Bubble Map** (`double_bubble_map`)
- **Fields**: `left`, `right` (both required)
- **Backend**: `routers/voice.py` line 973-986
- **Frontend**: `static/js/editor/interactive-editor.js` line 379-392
- **LLM Prompt**: `services/voice_agent.py` line 331-345
- **Example**: `{"action": "update_center", "left": "苹果", "right": "梨子", "target": "苹果和梨子"}`

### 2. **Flow Map** (`flow_map`)
- **Fields**: `title`
- **Backend**: `routers/voice.py` line 987-994
- **Frontend**: `static/js/editor/interactive-editor.js` line 394-403
- **LLM Prompt**: `services/voice_agent.py` line 346-358
- **Example**: `{"action": "update_center", "title": "Process Name", "target": "Process Name"}`

### 3. **Multi-Flow Map** (`multi_flow_map`)
- **Fields**: `event`
- **Backend**: `routers/voice.py` line 995-1002
- **Frontend**: `static/js/editor/interactive-editor.js` line 405-413
- **LLM Prompt**: `services/voice_agent.py` line 359-371
- **Example**: `{"action": "update_center", "event": "辛亥革命", "target": "辛亥革命"}`

### 4. **Brace Map** (`brace_map`)
- **Fields**: `whole`
- **Backend**: `routers/voice.py` line 1003-1010
- **Frontend**: `static/js/editor/interactive-editor.js` line 415-423
- **LLM Prompt**: `services/voice_agent.py` line 372-384
- **Example**: `{"action": "update_center", "whole": "Whole Name", "target": "Whole Name"}`

### 5. **Bridge Map** (`bridge_map`)
- **Fields**: `dimension`
- **Backend**: `routers/voice.py` line 1011-1018
- **Frontend**: `static/js/editor/interactive-editor.js` line 425-433
- **LLM Prompt**: `services/voice_agent.py` line 385-396
- **Example**: `{"action": "update_center", "dimension": "Dimension Name", "target": "Dimension Name"}`

### 6. **Default Diagrams** (use `target` → `new_text`)
- **Diagrams**: `mindmap`, `tree_map`, `circle_map`, `bubble_map`, `concept_map`
- **Fields**: `target` (maps to `new_text` in backend, `topic` in frontend)
- **Backend**: `routers/voice.py` line 1019-1026
- **Frontend**: `static/js/editor/interactive-editor.js` line 435-465
- **LLM Prompt**: `services/voice_agent.py` line 397-462
- **Example**: `{"action": "update_center", "target": "Topic Name"}`

**Special Frontend Handling:**
- **Mindmap**: Also updates `_layout.positions['topic'].text` (line 447-450)
- **Circle Map & Concept Map**: Also updates `_layout.positions` key (line 454-465)

---

## Add Node (`add_node`) Fields

### 1. **Double Bubble Map** (`double_bubble_map`)
- **Fields**: `category` (required)
- **Values**: `"similarities"`, `"left_differences"`, `"right_differences"`
- **Backend**: `routers/voice.py` line 1238-1241, 1269-1272
- **Frontend**: `static/js/editor/interactive-editor.js` line 716-731
- **LLM Prompt**: `services/voice_agent.py` line 572-575
- **Example**: `{"action": "add_node", "target": "color", "category": "similarities", "node_index": 0}`

### 2. **Multi-Flow Map** (`multi_flow_map`)
- **Fields**: `category` (required)
- **Values**: `"causes"`, `"effects"`
- **Backend**: `routers/voice.py` line 1238-1241, 1269-1272
- **Frontend**: `static/js/editor/interactive-editor.js` line 732-757
- **LLM Prompt**: `services/voice_agent.py` line 576-578
- **Example**: `{"action": "add_node", "target": "rain", "category": "causes", "node_index": 0}`

### 3. **Bridge Map** (`bridge_map`)
- **Fields**: `left`, `right` (both required for analogies)
- **Backend**: `routers/voice.py` line 1243-1248, 1274-1279
- **Frontend**: `static/js/editor/interactive-editor.js` line 758-806
- **LLM Prompt**: `services/voice_agent.py` line 580-582
- **Example**: `{"action": "add_node", "target": "wheel : car", "left": "wheel", "right": "car", "node_index": 0}`

### 4. **Flow Map** (`flow_map`)
- **Fields**: `step_index`, `substep_index` (for sub-steps)
- **Backend**: `routers/voice.py` line 1195-1285 (substep handling)
- **Frontend**: `static/js/editor/interactive-editor.js` line 808-922 (substep handling)
- **LLM Prompt**: `services/voice_agent.py` line 572-575 (updated with substep examples)
- **Examples**:
  - Step: `{"action": "add_node", "target": "prepare", "node_index": 0}`
  - Sub-step: `{"action": "add_node", "target": "gather materials", "step_index": 0, "substep_index": 0}`

### 5. **Tree Map** (`tree_map`)
- **Fields**: `category_index`, `item_index` (for hierarchical structure)
- **Backend**: `routers/voice.py` line 1196-1275 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 854-1065 (✅ **IMPLEMENTED**)
- **LLM Prompt**: `services/voice_agent.py` line 420-432 (✅ **UPDATED** with hierarchical indices)
- **Structure**: Categories are in `children` array, items are nested in `children[].children`
- **Examples**:
  - Category: `{"action": "add_node", "target": "mammals", "node_index": 0}` (adds to `children`)
  - Item: `{"action": "add_node", "target": "dogs", "category_index": 0, "item_index": 0}` (adds to `children[0].children`)

### 6. **Brace Map** (`brace_map`)
- **Fields**: `part_index`, `subpart_index` (for hierarchical structure)
- **Backend**: `routers/voice.py` line 1277-1356 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 1066-1127 (✅ **IMPLEMENTED**)
- **LLM Prompt**: `services/voice_agent.py` line 381-393 (✅ **UPDATED** with hierarchical indices)
- **Structure**: Parts are in `parts` array, subparts are nested in `parts[].subparts`
- **Examples**:
  - Part: `{"action": "add_node", "target": "engine", "node_index": 0}` (adds to `parts`)
  - Subpart: `{"action": "add_node", "target": "cylinders", "part_index": 0, "subpart_index": 0}` (adds to `parts[0].subparts`)

### 7. **Mindmap** (`mindmap`)
- **Fields**: `branch_index`, `child_index` (for hierarchical structure)
- **Backend**: `routers/voice.py` line 1358-1437 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 1128-1190 (✅ **IMPLEMENTED**)
- **LLM Prompt**: `services/voice_agent.py` line 406-419 (✅ **UPDATED** with hierarchical indices)
- **Structure**: Branches are in `children` array, sub-branches are nested in `children[].children`
- **Examples**:
  - Branch: `{"action": "add_node", "target": "fruits", "node_index": 0}` (adds to `children`)
  - Child: `{"action": "add_node", "target": "apples", "branch_index": 0, "child_index": 0}` (adds to `children[0].children`)

### 8. **Concept Map** (`concept_map`)
- **Fields**: `from`, `to`, `label` (for relationships), `relationship_index` (for update/delete)
- **Backend**: `routers/voice.py` line 1439-1518 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 1191-1253 (✅ **IMPLEMENTED**)
- **LLM Prompt**: `services/voice_agent.py` line 459-467 (✅ **UPDATED** with relationship fields)
- **Structure**: Concepts are in `concepts` array, relationships are in `relationships` array
- **Examples**:
  - Concept: `{"action": "add_node", "target": "Concept1", "node_index": 0}` (adds to `concepts`)
  - Relationship: `{"action": "add_node", "from": "Concept1", "to": "Concept2", "label": "causes"}` (adds to `relationships`)

### 9. **All Other Diagrams** (Standard)
- **Diagrams**: `circle_map`, `bubble_map`
- **Fields**: `target` (standard)
- **Backend**: `routers/voice.py` line 1256-1285
- **Frontend**: `static/js/editor/interactive-editor.js` line 923-960
- **Example**: `{"action": "add_node", "target": "Node Text", "node_index": 0}`

---

## Update Node (`update_node`) Fields

### 1. **Double Bubble Map** (`double_bubble_map`)
- **Fields**: `category` (supported)
- **Values**: `"similarities"`, `"left_differences"`, `"right_differences"`
- **Backend**: `routers/voice.py` line 1128-1131
- **Frontend**: `static/js/editor/interactive-editor.js` line 485-555
- **Example**: `{"action": "update_node", "target": "color", "node_index": 0, "category": "similarities"}`

### 2. **Multi-Flow Map** (`multi_flow_map`)
- **Fields**: `category` (supported)
- **Values**: `"causes"`, `"effects"`
- **Backend**: `routers/voice.py` line 1128-1131
- **Frontend**: `static/js/editor/interactive-editor.js` line 556-605
- **Example**: `{"action": "update_node", "target": "rain", "node_index": 0, "category": "causes"}`

### 3. **Bridge Map** (`bridge_map`)
- **Fields**: `left`, `right` (supported)
- **Backend**: `routers/voice.py` line 1133-1138
- **Frontend**: `static/js/editor/interactive-editor.js` line 606-650
- **Example**: `{"action": "update_node", "target": "wheel : car", "left": "wheel", "right": "car", "node_index": 0}`

### 4. **Flow Map** (`flow_map`)
- **Fields**: `step_index`, `substep_index` (supported for sub-steps)
- **Backend**: `routers/voice.py` line 1093-1185 (substep handling)
- **Frontend**: `static/js/editor/interactive-editor.js` line 651-703 (substep handling)
- **Examples**:
  - Step: `{"action": "update_node", "target": "prepare", "node_index": 0}`
  - Sub-step: `{"action": "update_node", "target": "check inventory", "step_index": 0, "substep_index": 1}`

### 5. **Tree Map** (`tree_map`)
- **Fields**: `category_index`, `item_index` (✅ **IMPLEMENTED**)
- **Backend**: `routers/voice.py` line 1100-1144 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 651-703 (✅ **IMPLEMENTED**)
- **Structure**: Supports updating categories and items within categories
- **Examples**:
  - Category: `{"action": "update_node", "target": "mammals", "node_index": 0}`
  - Item: `{"action": "update_node", "target": "dogs", "category_index": 0, "item_index": 0}`

### 6. **Brace Map** (`brace_map`)
- **Fields**: `part_index`, `subpart_index` (✅ **IMPLEMENTED**)
- **Backend**: `routers/voice.py` line 1146-1190 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 651-703 (✅ **IMPLEMENTED**)
- **Structure**: Supports updating parts and subparts within parts
- **Examples**:
  - Part: `{"action": "update_node", "target": "engine", "node_index": 0}`
  - Subpart: `{"action": "update_node", "target": "cylinders", "part_index": 0, "subpart_index": 0}`

### 7. **Mindmap** (`mindmap`)
- **Fields**: `branch_index`, `child_index` (✅ **IMPLEMENTED**)
- **Backend**: `routers/voice.py` line 1192-1236 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 651-703 (✅ **IMPLEMENTED**)
- **Structure**: Supports updating branches and children within branches
- **Examples**:
  - Branch: `{"action": "update_node", "target": "fruits", "node_index": 0}`
  - Child: `{"action": "update_node", "target": "apples", "branch_index": 0, "child_index": 0}`

### 8. **Concept Map** (`concept_map`)
- **Fields**: `from`, `to`, `label` (for relationships), `relationship_index` (✅ **IMPLEMENTED**)
- **Backend**: `routers/voice.py` line 1238-1282 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 651-703 (✅ **IMPLEMENTED**)
- **Structure**: Supports updating concepts and relationships
- **Examples**:
  - Concept: `{"action": "update_node", "target": "Concept1", "node_index": 0}`
  - Relationship: `{"action": "update_node", "target": "leads to", "relationship_index": 0}` or `{"action": "update_node", "from": "Concept1", "to": "Concept2", "label": "causes", "relationship_index": 0}`

### 9. **All Other Diagrams** (Standard)
- **Diagrams**: `circle_map`, `bubble_map`
- **Fields**: `node_id`, `new_text` (standard)
- **Backend**: `routers/voice.py` line 1121-1144
- **Frontend**: `static/js/editor/interactive-editor.js` line 651-703
- **Example**: `{"action": "update_node", "target": "New Text", "node_index": 0}`

---

## Delete Node (`delete_node`) Fields

### 1. **Double Bubble Map** (`double_bubble_map`)
- **Fields**: `category` (supported)
- **Values**: `"similarities"`, `"left_differences"`, `"right_differences"`
- **Backend**: `routers/voice.py` line 1350-1356
- **Frontend**: `static/js/editor/interactive-editor.js` line 856-888
- **Example**: `{"action": "delete_node", "node_index": 0, "category": "similarities"}`

### 2. **Multi-Flow Map** (`multi_flow_map`)
- **Fields**: `category` (supported)
- **Values**: `"causes"`, `"effects"`
- **Backend**: `routers/voice.py` line 1350-1356
- **Frontend**: `static/js/editor/interactive-editor.js` line 889-920
- **Example**: `{"action": "delete_node", "node_index": 0, "category": "causes"}`

### 3. **Flow Map** (`flow_map`)
- **Fields**: `step_index`, `substep_index` (supported for sub-steps)
- **Backend**: `routers/voice.py` line 1401-1457 (substep handling)
- **Frontend**: `static/js/editor/interactive-editor.js` line 921-970 (substep handling)
- **Examples**:
  - Step: `{"action": "delete_node", "node_index": 0}`
  - Sub-step: `{"action": "delete_node", "step_index": 0, "substep_index": 1}`

### 4. **Tree Map** (`tree_map`)
- **Fields**: `category_index`, `item_index` (✅ **IMPLEMENTED**)
- **Backend**: `routers/voice.py` line 1463-1503 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 1020-1065 (✅ **IMPLEMENTED**)
- **Structure**: Supports deleting categories and items within categories
- **Examples**:
  - Category: `{"action": "delete_node", "node_index": 0}`
  - Item: `{"action": "delete_node", "category_index": 0, "item_index": 0}`

### 5. **Brace Map** (`brace_map`)
- **Fields**: `part_index`, `subpart_index` (✅ **IMPLEMENTED**)
- **Backend**: `routers/voice.py` line 1505-1545 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 1066-1127 (✅ **IMPLEMENTED**)
- **Structure**: Supports deleting parts and subparts within parts
- **Examples**:
  - Part: `{"action": "delete_node", "node_index": 0}`
  - Subpart: `{"action": "delete_node", "part_index": 0, "subpart_index": 0}`

### 6. **Mindmap** (`mindmap`)
- **Fields**: `branch_index`, `child_index` (✅ **IMPLEMENTED**)
- **Backend**: `routers/voice.py` line 1547-1587 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 1128-1190 (✅ **IMPLEMENTED**)
- **Structure**: Supports deleting branches and children within branches
- **Examples**:
  - Branch: `{"action": "delete_node", "node_index": 0}`
  - Child: `{"action": "delete_node", "branch_index": 0, "child_index": 0}`

### 7. **Bridge Map** (`bridge_map`)
- **Fields**: Standard (`node_id`)
- **Backend**: `routers/voice.py` line 1426-1457
- **Frontend**: `static/js/editor/interactive-editor.js` line 921-970
- **Example**: `{"action": "delete_node", "node_index": 0}`

### 8. **Concept Map** (`concept_map`)
- **Fields**: `concept_index`, `relationship_index` (✅ **IMPLEMENTED**)
- **Backend**: `routers/voice.py` line 1589-1629 (✅ **IMPLEMENTED**)
- **Frontend**: `static/js/editor/interactive-editor.js` line 1191-1253 (✅ **IMPLEMENTED**)
- **Structure**: Supports deleting concepts and relationships
- **Examples**:
  - Concept: `{"action": "delete_node", "node_index": 0}`
  - Relationship: `{"action": "delete_node", "relationship_index": 0}`

### 9. **All Other Diagrams** (Standard)
- **Diagrams**: `circle_map`, `bubble_map`
- **Fields**: `node_id` (standard)
- **Backend**: `routers/voice.py` line 1426-1457
- **Frontend**: `static/js/editor/interactive-editor.js` line 971-980
- **Example**: `{"action": "delete_node", "node_index": 0}`

---

## Field Priority in Backend Processing

When processing `update_center`, the backend checks fields in this order:

1. **Diagram-specific field first** (e.g., `event` for multi-flow map, `title` for flow map)
2. **Fallback to `target`** if diagram-specific field is missing
3. **Fallback to `new_text`** if both are missing
4. **Return `False`** with warning if none are found

**Code Location**: `routers/voice.py` line 966-1026

---

## Complete Summary Table

| Diagram Type | Update Center Field | Add Node Special Fields | Update Node Special Fields | Delete Node Special Fields | Node Types | Hierarchical Support |
|-------------|---------------------|------------------------|---------------------------|---------------------------|------------|---------------------|
| `circle_map` | `target` → `new_text` | None | Standard | Standard | `context` (flat) | ❌ |
| `bubble_map` | `target` → `new_text` | None | Standard | Standard | `attributes` (flat) | ❌ |
| `double_bubble_map` | `left`, `right` | `category`: `similarities`, `left_differences`, `right_differences` | `category` | `category` | `similarities`, `left_differences`, `right_differences` (categorized) | ❌ |
| `tree_map` | `target` → `new_text` | ✅ `category_index`, `item_index` | ✅ `category_index`, `item_index` | ✅ `category_index`, `item_index` | `children` (hierarchical: categories with items) | ✅ |
| `flow_map` | `title` | `step_index`, `substep_index` | `step_index`, `substep_index` | `step_index`, `substep_index` | `steps` (flat) + `substeps` (hierarchical) | ✅ |
| `multi_flow_map` | `event` | `category`: `causes`, `effects` | `category` | `category` | `causes`, `effects` (categorized) | ❌ |
| `brace_map` | `whole` | ✅ `part_index`, `subpart_index` | ✅ `part_index`, `subpart_index` | ✅ `part_index`, `subpart_index` | `parts` (hierarchical: parts with subparts) | ✅ |
| `bridge_map` | `dimension` | `left`, `right` (for analogies) | `left`, `right` | Standard | `analogies` (pairs) | ❌ |
| `mindmap` | `target` → `new_text` | ✅ `branch_index`, `child_index` | ✅ `branch_index`, `child_index` | ✅ `branch_index`, `child_index` | `children` (hierarchical: branches with children) | ✅ |
| `concept_map` | `target` → `new_text` | ✅ `from`, `to`, `label` (for relationships) | ✅ `from`, `to`, `label`, `relationship_index` | ✅ `concept_index`, `relationship_index` | `concepts` (flat) + `relationships` (edges) | ✅ |

**Legend:**
- ✅ **Fully Supported**: Field is fully implemented and working
- ⚠️ **Not Yet Implemented**: Field is documented but not yet implemented in backend/frontend
- **Standard**: Uses generic `node_id` + `new_text` approach
- ❌ **No Hierarchical Support**: Diagram has flat structure
- ⚠️ **Partial Hierarchical Support**: Diagram has hierarchical structure but voice agent doesn't fully support it yet

---

## Implementation Files

1. **LLM Prompt Definitions**: `services/voice_agent.py` (line 329-467)
2. **Backend Command Processing**: `routers/voice.py` (line 950-1457)
3. **Frontend Update Handlers**: `static/js/editor/interactive-editor.js` (line 375-980)

---

## Notes

- All diagrams support `node_index` for position-based node operations (for top-level nodes)
- Hierarchical diagrams require multiple indices (e.g., `step_index` + `substep_index` for flow maps)
- The `target` field is always included in LLM responses for backward compatibility
- Frontend handlers prioritize diagram-specific fields over generic `target`/`new_text`
- Backend `execute_diagram_update` function handles field extraction and fallback logic

## Known Limitations

None! All hierarchical operations are now fully implemented for all diagram types.

## Implementation Status

✅ **All diagrams now fully support hierarchical operations:**

1. **Tree Map**: ✅ Fully supported - `category_index` and `item_index` are implemented for all operations.
2. **Brace Map**: ✅ Fully supported - `part_index` and `subpart_index` are implemented for all operations.
3. **Mindmap**: ✅ Fully supported - `branch_index` and `child_index` are implemented for all operations.
4. **Concept Map**: ✅ Fully supported - Relationship operations (`from`, `to`, `label`, `relationship_index`) are implemented for all operations.
5. **Flow Map**: ✅ Fully supported - `step_index` and `substep_index` are implemented for all operations.
6. **Double Bubble Map & Multi-Flow Map**: ✅ Fully supported - `category` field is implemented for all operations.
7. **Bridge Map**: ✅ Fully supported - `left`/`right` fields are implemented for add/update operations.
