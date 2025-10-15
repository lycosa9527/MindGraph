# Double Bubble Map Node Palette - Architecture Reference

**✅ IMPLEMENTATION COMPLETED - October 15, 2025**

## 🎯 Implementation Status

✅ **Backend**: `double_bubble_palette.py` generator with similarities and differences modes  
✅ **API Routes**: Full support in `/thinking_mode/node_palette/*` endpoints  
✅ **Request Models**: Mode parameter added to all node palette requests  
✅ **Frontend Manager**: Tab management, pair cards, and mode switching  
✅ **CSS Styles**: Professional tab UI and pair card styling with dark mode  
✅ **HTML Template**: Tab switcher UI integrated into editor  

---

## 🎨 Architecture Overview

### Modular Smart Node System

The node palette uses a **configuration-driven architecture** that supports:
- ✅ Single array diagrams (Circle Map, Bubble Map)
- ✅ Multi-array diagrams with tabs (Double Bubble Map)
- 🔮 Future: Multi-Flow Map, Tree Map, etc.

### Three Fundamental Array Patterns

```javascript
// Pattern A: Simple/Independent Arrays (Circle, Bubble, Flow, Mind)
spec.arrayName = ["item1", "item2", "item3"];

// Pattern B: Paired Arrays with STRICT alignment (Double Bubble differences)
spec.leftArray = ["A1", "A2"];
spec.rightArray = ["B1", "B2"];  // leftArray[i] ↔ rightArray[i]

// Pattern C: Multiple Independent Arrays (Multi-Flow Map)
spec.causes = ["cause1", "cause2"];
spec.effects = ["effect1", "effect2", "effect3"];  // NO alignment
```

---

## 📊 Diagram Inventory & Array Structures

### Simple: Single Array Diagrams
1. ✅ **Circle Map**: `spec.context[]` - Context nodes around topic
2. ✅ **Bubble Map**: `spec.attributes[]` - Attribute/adjective nodes
3. **Flow Map**: `spec.steps[]` - Sequential step nodes
4. **Mind Map**: `spec.branches[]` - Branch nodes
5. **Bridge Map**: `spec.analogies[]` - Analogy pairs (left/right items)

### Complex: Multi-Array Diagrams

**Type A: Independent Arrays** (separate tabs, no alignment needed)
6. **Multi-Flow Map**: 
   - `spec.event` - Central event (single string)
   - `spec.causes[]` - Independent array of causes
   - `spec.effects[]` - Independent array of effects
   - ⚠️ **Key:** causes[0] and effects[0] are NOT related!

7. **Tree Map**:
   - `spec.categories[]` - Each category has nested `items[]`
   - Hierarchical, not flat arrays

**Type B: Paired Arrays** (must maintain index alignment)
8. ✅ **Double Bubble Map**:
   - `spec.similarities[]` - Independent array
   - `spec.left_differences[]` - PAIRED with right_differences[]
   - `spec.right_differences[]` - PAIRED with left_differences[]
   - ⚠️ **Critical:** left_differences[0] <-> right_differences[0] are ALIGNED

**Special: Graph Structures**
9. **Concept Map**:
   - `spec.nodes[]` - Node objects with {id, text, x, y}
   - `spec.connections[]` - Edge objects with {from, to, label}
   - Not simple arrays, graph data structure

10. **Brace Map**:
    - `spec.parts[]` - Top-level parts
    - Each part has nested `subparts[]`
    - Hierarchical structure

---

## 📋 Comparison Table: Array Types & Requirements

| Diagram Type | Array Count | Array Names | Array Type | Alignment? | Node Type(s) |
|--------------|-------------|-------------|------------|------------|--------------|
| **Circle Map** | 1 | `context[]` | Simple | N/A | `context` |
| **Bubble Map** | 1 | `attributes[]` | Simple | N/A | `attribute` |
| **Flow Map** | 1 | `steps[]` | Sequential | N/A | `step` |
| **Mind Map** | 1 | `branches[]` | Simple | N/A | `branch` |
| **Double Bubble** | 3 | `similarities[]`<br/>`left_differences[]`<br/>`right_differences[]` | Mixed:<br/>• similarities: Independent<br/>• differences: **PAIRED** | **YES**<br/>left[i] ↔ right[i] | `similarity`<br/>`difference` |
| **Multi-Flow** | 3 | `event` (string)<br/>`causes[]`<br/>`effects[]` | Independent | **NO**<br/>causes[i] ≠ effects[i] | `event`<br/>`cause`<br/>`effect` |
| **Tree Map** | Hierarchical | `categories[]`<br/>└─ `items[]` | Nested | Category-level | `category`<br/>`leaf` |
| **Brace Map** | Hierarchical | `parts[]`<br/>└─ `subparts[]` | Nested | Part-level | `part`<br/>`subpart` |
| **Bridge Map** | 1 (but paired items) | `analogies[]` | Paired objects | Each item has left/right | `analogy` |
| **Concept Map** | 2 | `nodes[]`<br/>`connections[]` | Graph | Connections reference nodes | `concept`<br/>`connection` |

---

## 🔑 Key Implementation Details

### Backend: Double Bubble Palette Generator

**Location**: `agents/thinking_modes/node_palette/double_bubble_palette.py`

**Two Generation Modes**:
1. **Similarities Mode** (`mode='similarities'`):
   - Generates individual shared attributes
   - Output: One string per line
   - Example: "Furry", "Four legs", "Have tails"

2. **Differences Mode** (`mode='differences'`):
   - Generates paired contrasting attributes
   - Output: JSON objects with `left` and `right` properties
   - Example: `{"left": "Meow", "right": "Bark"}`

**Language Support**: English and Chinese with automatic detection

### Frontend: Tab Management

**Location**: `static/js/editor/node-palette-manager.js`

**Key Features**:
- Tab state management: `currentTab`, `tabNodes`, `tabSelectedNodes`
- Smooth tab switching with fade animations
- Separate node collections per tab
- Mode parameter passed to backend based on current tab

**Metadata Configuration**:
```javascript
    'double_bubble_map': {
        arrays: {
            'similarities': {
                nodeName: 'similarity',
                nodeNamePlural: 'similarities',
                nodeType: 'similarity'
            },
            'left_differences': {
                nodeName: 'left difference',
                nodeNamePlural: 'left differences',
                nodeType: 'left_difference'
            },
            'right_differences': {
                nodeName: 'right difference',
                nodeNamePlural: 'right differences',
                nodeType: 'right_difference'
            }
        },
    useTabs: true
}
```

### UI Components

**Tab Switcher** (`templates/editor.html`):
- 🔗 Similarities tab with node counter
- ⚖️ Differences tab with pair counter
- Sliding indicator animation
- Hidden by default, shown only for double bubble map

**Pair Cards** (`static/css/node-palette.css`):
- Circular nodes for left and right topics
- Gradient connection line between nodes
- LLM-specific color themes
- Hover effects and selection states
- Full dark mode support

---

## 🔮 Future Extension Path

The architecture is ready for additional diagrams:

**Multi-Flow Map** (Next candidate):
- Add `multi_flow_palette.py` generator
- Configure two modes: 'causes' and 'effects'
- Reuse existing tab system
- No changes to core architecture needed

**Hierarchical Diagrams** (Tree Map, Brace Map):
- Will need `processHierarchicalArray()` method
- Different UI approach (nested structure)
- Backend already supports via `BasePaletteGenerator`

**Graph Structures** (Concept Map):
- Will need `processGraphStructure()` method
- Node + edge generation
- More complex UI requirements

---

## 📚 Related Documentation

- `NODE_PALETTE_SESSION_MANAGEMENT_CODE_REVIEW.md` - Session management architecture
- `API_REFERENCE.md` - Full API documentation
- `API_KEY_SECURITY_IMPLEMENTATION.md` - Security implementation

---

**Author**: lycosa9527  
**Made by**: MindSpring Team  
**Last Updated**: October 15, 2025
