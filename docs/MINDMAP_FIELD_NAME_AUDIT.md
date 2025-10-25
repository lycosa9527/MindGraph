# Mind Map Field Name Audit

**Date:** 2025-10-19  
**Status:** ✅ ALL FIELD NAMES CORRECT  
**Purpose:** Verify field name consistency for Mind Map throughout the system

---

## Field Name Verification

### ✅ **Spec Structure: Uses `topic`**

**Mind Map Spec Format**:
```json
{
    "topic": "Main Topic",
    "children": [
        {
            "label": "Branch 1",
            "children": [...]
        }
    ]
}
```

---

## Component-by-Component Audit

### 1. ✅ Mind Map Agent (`agents/mind_maps/mind_map_agent.py`)

**Validation** (Line 172):
```python
if 'topic' not in spec or not spec['topic']:
    return False, "Missing topic"
```

**Enhancement** (Line 331):
```python
if 'topic' not in spec or not spec['topic']:
    return {"success": False, "error": "Missing topic"}
```

**Layout Generation** (Line 341):
```python
layout = self._generate_mind_map_layout(spec['topic'], spec['children'])
```

**Status**: ✅ Uses `'topic'` consistently

---

### 2. ✅ ThinkGuide React Agent (`agents/thinking_modes/mindmap_agent_react.py`)

**Pure Discussion** (Line 168):
```python
topic = diagram_data.get('topic', 'this topic')
branches = diagram_data.get('children', [])
```

**Handle Node Palette** (Line 233):
```python
center_topic = diagram_data.get('topic', 'Unknown Topic')
```

**Status Statistics** (Line 284):
```python
topic = diagram_data.get('topic', '')
branches = diagram_data.get('children', [])
```

**Status**: ✅ Reads `'topic'` from diagram_data

---

### 3. ✅ Frontend ThinkGuide Manager (`static/js/editor/thinking-mode-manager.js`)

**Normalize Diagram Data** (Lines 541-545):
```javascript
case 'mindmap':
    return {
        topic: spec.topic || '',
        children: spec.children || []
    };
```

**Node Palette Topic Extraction** (Lines 868-869):
```javascript
} else if (this.diagramType === 'tree_map' || this.diagramType === 'mindmap') {
    centerTopic = diagramData?.topic;
}
```

**Update Center Topic** (Lines 1184-1186):
```javascript
if (editor.currentSpec.topic !== undefined) {
    editor.currentSpec.topic = newText;
}
```

**Status**: ✅ Uses and reads `'topic'` field

---

### 4. ✅ Backend Router (`routers/thinking.py`)

**Node Palette Center Topic** (Lines 203-205):
```python
elif req.diagram_type == 'tree_map' or req.diagram_type == 'mindmap':
    # Tree map and mindmap use topic
    center_topic = req.diagram_data.get('topic', '')
```

**Status**: ✅ Reads `'topic'` from request

---

### 5. ✅ Mind Map Palette Generator (`agents/thinking_modes/node_palette/mindmap_palette.py`)

**Reads center_topic** (parameter passed from router):
```python
async def generate_batch(
    self,
    session_id: str,
    center_topic: str,  # <-- This is extracted from spec['topic']
    ...
)
```

**Status**: ✅ Receives topic via center_topic parameter

---

## Data Flow Verification

```
1. Mind Map Agent generates spec
   ↓
   spec = {"topic": "Main Topic", "children": [...]}
   
2. Frontend receives spec → Stores in editor.currentSpec
   ↓
   editor.currentSpec.topic = "Main Topic"
   
3. ThinkGuide extracts diagram data
   ↓
   normalizeDiagramData() returns {"topic": "Main Topic", "children": [...]}
   
4. ThinkGuide sends to backend
   ↓
   POST /api/thinking/stream with diagram_data: {"topic": "Main Topic", ...}
   
5. Backend React Agent receives
   ↓
   diagram_data.get('topic') = "Main Topic" ✓
   
6. Node Palette opened
   ↓
   centerTopic = diagramData?.topic = "Main Topic" ✓
   
7. Backend Node Palette route
   ↓
   center_topic = req.diagram_data.get('topic') = "Main Topic" ✓
   
8. Palette Generator receives
   ↓
   center_topic = "Main Topic" ✓
```

---

## Field Name Summary

| Component | Field Name | Status |
|-----------|-----------|--------|
| Mind Map Agent (generation) | `'topic'` | ✅ Correct |
| Mind Map Agent (validation) | `'topic'` | ✅ Correct |
| Mind Map Agent (layout) | `'topic'` | ✅ Correct |
| ThinkGuide React Agent | `'topic'` | ✅ Correct |
| Frontend ThinkGuide (normalize) | `'topic'` | ✅ Correct |
| Frontend ThinkGuide (extract) | `'topic'` | ✅ Correct |
| Backend Router | `'topic'` | ✅ Correct |
| Node Palette Generator | `center_topic` (param) | ✅ Correct |

---

## Conclusion

✅ **ALL FIELD NAMES ARE CONSISTENT**

Mind Map uses `'topic'` throughout the entire system:
- Backend generation: `spec['topic']`
- Backend validation: `'topic' in spec`
- Backend React agent: `diagram_data.get('topic')`
- Frontend normalization: `spec.topic`
- Frontend extraction: `diagramData?.topic`
- Backend router: `req.diagram_data.get('topic')`

**No field name mismatches detected.**

---

## If ThinkGuide Can't Read Main Topic

If ThinkGuide is unable to read the main topic, the issue is **NOT** field name mismatch. Possible causes:

1. **Empty Spec**: `editor.currentSpec` might be null/undefined
2. **Template Issue**: Default template might have empty topic
3. **Timing Issue**: Spec not yet loaded when ThinkGuide reads it
4. **Data Type Issue**: Topic might be an object instead of string

### Debug Steps:

1. Check browser console for:
   ```
   [ThinkGuide] Normalizing diagram data: { topic: ... }
   ```

2. Verify `editor.currentSpec.topic` is not empty:
   ```javascript
   console.log(window.currentEditor?.currentSpec?.topic);
   ```

3. Check if spec was generated:
   ```javascript
   console.log(window.currentEditor?.currentSpec);
   ```

4. Verify diagram type:
   ```javascript
   console.log(window.currentEditor?.diagramType);
   ```

---

**Audit Date**: 2025-10-19  
**Result**: ✅ NO FIELD NAME ISSUES FOUND  
**All field references use `'topic'` consistently**

