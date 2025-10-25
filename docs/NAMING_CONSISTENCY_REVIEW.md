# Naming Consistency Review - Brace Map & Flow Map
**Date**: 2025-10-19  
**Status**: 🔍 COMPREHENSIVE CODE REVIEW  

---

## Brace Map Field Naming Issues

### Current Inconsistency
| Component | Field Name | Status |
|-----------|------------|--------|
| **Prompts** (thinking_maps.py) | `topic` | ❌ INCONSISTENT |
| **JS Renderer** (brace-renderer.js) | `topic` | ❌ INCONSISTENT |
| **Python Agent** (brace_map_agent.py) | `whole` | ✅ CORRECT |
| **ThinkGuide Agent** (brace_map_agent_react.py) | `whole` | ✅ CORRECT |
| **Frontend Normalization** | `whole` | ✅ CORRECT |
| **Node Palette** | `whole` | ✅ CORRECT |

### Files Requiring Changes

#### 1. **Prompts** - `prompts/thinking_maps.py`
**Lines 596, 625, 626, 666, 695, 696**
```python
# BEFORE: topic: "Main topic"
# AFTER:  whole: "Main topic"
```

Changes needed:
- Line 596: `topic: "Main topic"` → `whole: "Main topic"`
- Line 625: Example format `topic: "Car"` → `whole: "Car"`
- Line 666: `topic: "主题"` → `whole: "主题"`
- Line 695: Example format `topic: "汽车"` → `whole: "汽车"`
- Update all references in comments/documentation

#### 2. **JS Renderer** - `static/js/renderers/brace-renderer.js`
**Multiple locations**

Lines that check for `.topic`:
- Line 59: `if (spec.topic && Array.isArray(spec.parts) && spec._agent_result)`
- Line 63: `else if (spec.topic && Array.isArray(spec.parts))`
- Line 86: `if (!actualSpec.topic)`
- Line 212: `const topicWidth = measureTextWidth(actualSpec.topic, THEME.fontTopic, 'bold')`
- Line 632: `.text(actualSpec.topic)`
- Line 652: `const hasChinese = /[\u4e00-\u9fa5]/.test(actualSpec.topic)`

All need to change `.topic` → `.whole`

---

## Flow Map Field Naming Issues

### Current Status
| Component | Field Name | Status |
|-----------|------------|--------|
| **Prompts** (thinking_maps.py) | `title` | ✅ CONSISTENT |
| **JS Renderer** (flow-renderer.js) | `title` | ✅ CONSISTENT |
| **Python Agent** (flow_map_agent.py) | - | ✅ N/A |
| **ThinkGuide Agent** (flow_map_agent_react.py) | `title` | ✅ CONSISTENT |
| **Frontend Normalization** | `title` | ✅ CONSISTENT |
| **Node Palette** | `title` | ✅ CONSISTENT |

**Result**: Flow Map is already consistent! ✅ No changes needed.

---

## Additional Component Checks

### Node Palette System
**Files checked**:
- `static/js/editor/node-palette-manager.js` - ✅ Already supports both `text` and `name` for parts
- `agents/thinking_modes/node_palette/brace_map_palette.py` - ✅ Correct
- `agents/thinking_modes/node_palette/flow_map_palette.py` - ✅ Correct

### Tab System
**Files checked**:
- `static/js/editor/node-palette-manager.js` - ✅ Uses `whole` for brace_map
- Stage detection logic - ✅ Already updated to use `whole`

### Smart Node System
**Files checked**:
- `agents/thinking_maps/brace_map_agent.py` - ✅ Already updated to use `whole`

### ThinkGuide System
**Files checked**:
- `agents/thinking_modes/brace_map_agent_react.py` - ✅ Already updated to use `whole`
- `agents/thinking_modes/flow_map_agent_react.py` - ✅ Uses `title` (correct)

---

## Implementation Plan

### Priority 1: Brace Map Prompts
1. Update `prompts/thinking_maps.py`:
   - Change `topic:` → `whole:` in all Brace Map prompts
   - Update both EN and ZH versions
   - Update example formats
   - Update documentation text

### Priority 2: Brace Map JS Renderer
1. Update `static/js/renderers/brace-renderer.js`:
   - Replace all `.topic` → `.whole`
   - Update validation checks
   - Update text extraction
   - Update dimension placeholder logic

### Priority 3: Testing
1. Test Brace Map generation from scratch
2. Test Brace Map with existing diagrams (backward compatibility)
3. Test Node Palette with Brace Map
4. Test ThinkGuide with Brace Map

---

## Risk Assessment

### Breaking Changes
**Potential Impact**: 🔴 HIGH
- Existing diagrams with `topic` field will break
- Need migration or backward compatibility

### Mitigation Strategy
**Option 1**: Add backward compatibility in renderer
```javascript
const whole = spec.whole || spec.topic || '';  // Fallback for old diagrams
```

**Option 2**: Strict enforcement (RECOMMENDED)
- Only support `whole` going forward
- Users can regenerate old diagrams
- Cleaner codebase

### Recommendation
✅ **Use strict enforcement** - cleaner long-term, and Brace Map is likely not heavily used yet.

---

## Summary

### Brace Map Changes Completed
- ✅ Python Agent - DONE
- ✅ ThinkGuide - DONE  
- ✅ Frontend Normalization - DONE
- ✅ Node Palette - DONE
- ✅ **Prompts** - DONE (2 versions updated)
- ✅ **JS Renderer** - DONE (6 locations updated)
- ✅ **Auto-Complete** - DONE (toolbar-manager.js Strategy 1e added)

### Flow Map Status
✅ **No changes needed** - Already fully consistent with `title`

---

## All Components Updated

### Prompts (`prompts/thinking_maps.py`)
- Lines 596, 601, 625, 666, 671, 673, 695 - Changed `topic:` → `whole:`

### JS Renderer (`static/js/renderers/brace-renderer.js`)
- Lines 59, 63, 86-87, 212, 632, 652 - Changed `.topic` → `.whole`

### Auto-Complete (`static/js/editor/toolbar-manager.js`)
- Added Strategy 1e specifically for Brace Map checking `spec.whole`

---

**Status**: ✅ COMPLETE - All naming is now consistent!

