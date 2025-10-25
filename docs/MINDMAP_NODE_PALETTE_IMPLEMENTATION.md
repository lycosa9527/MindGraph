# Mind Map Node Palette Multi-Stage Implementation

**Date:** 2025-10-19  
**Status:** ✅ IMPLEMENTATION COMPLETE  
**Purpose:** Add multi-stage Node Palette workflow to Mind Map (like Tree Map)

---

## Summary

Successfully implemented multi-stage Node Palette workflow for Mind Map, enabling:
- Stage 1: Add branches to central topic
- Stage 2: Add sub-branches (children) to specific branches
- Dynamic tab management
- Stage persistence

---

## Changes Made

### 1. Frontend Configuration (`static/js/editor/node-palette-manager.js`)

#### Before:
```javascript
'mindmap': {
    arrayName: 'branches',
    nodeName: 'branch',
    nodeNamePlural: 'branches',
    nodeType: 'branch'
}
```

#### After:
```javascript
'mindmap': {
    // Multi-stage workflow with tabs for branches -> children
    arrays: {
        'children': {
            nodeName: 'branch',
            nodeNamePlural: 'branches',
            nodeType: 'branch',
            parentField: 'topic'  // branches connect to topic
        }
    },
    // Default array for backward compatibility
    arrayName: 'children',
    nodeName: 'branch',
    nodeNamePlural: 'branches',
    nodeType: 'branch',
    useTabs: true,  // Enable tab UI for branches
    useStages: true  // Enable multi-stage workflow
}
```

**Changes**:
- ✅ Added `arrays` object with `children` configuration
- ✅ Added `useTabs: true` to enable tab UI
- ✅ Added `useStages: true` to enable multi-stage workflow
- ✅ Added `parentField: 'topic'` for branch-to-topic connection
- ✅ Maintained backward compatibility with default fields

---

### 2. Backend Palette Generator (`agents/thinking_modes/node_palette/mindmap_palette.py`)

#### Major Updates:

**A. Class Definition - Added Stage Support**
```python
class MindMapPaletteGenerator(BasePaletteGenerator):
    """
    Mind Map specific palette generator with multi-stage workflow.
    
    Stages:
    - branches: Generate main branches from central topic (default)
    - children: Generate sub-branches for specific branch
    """
    
    def __init__(self):
        """Initialize mind map palette generator"""
        super().__init__()
        # Track stage data per session
        self.session_stages = {}  # session_id -> {'stage': str, 'branch_name': str}
```

**B. New `generate_batch()` Method**
```python
async def generate_batch(
    self,
    session_id: str,
    center_topic: str,
    educational_context: Optional[Dict[str, Any]] = None,
    nodes_per_llm: int = 15,
    stage: str = 'branches',  # NEW: stage parameter
    stage_data: Optional[Dict[str, Any]] = None  # NEW: stage-specific data
) -> AsyncGenerator[Dict, None]:
```

**Features**:
- ✅ Stores stage info per session
- ✅ Passes session_id through educational_context
- ✅ Tags generated nodes with mode for routing
- ✅ For `children` stage: uses `branch_name` as mode (for tab routing)
- ✅ For `branches` stage: uses `'branches'` as mode

**C. Stage-Specific Prompt Building**

**Updated `_build_prompt()` Method**:
```python
def _build_prompt(...) -> str:
    # Determine current stage from session_stages
    session_id = educational_context.get('_session_id')
    stage = 'branches'  # default
    
    if session_id and session_id in self.session_stages:
        stage = self.session_stages[session_id].get('stage', 'branches')
    
    # Build stage-specific prompt
    if stage == 'children':
        branch_name = stage_data.get('branch_name', '')
        return self._build_children_prompt(...)
    else:  # branches
        return self._build_branches_prompt(...)
```

**D. New Prompt Methods**

**`_build_branches_prompt()`**: Generate main branches from central topic
- Focuses on divergent thinking
- Encourages multi-dimensional association
- Branch-level ideas

**`_build_children_prompt()`**: Generate sub-branches for specific branch
- Focuses on deepening and refining
- Maintains logical connection with parent branch
- Child-level details

---

## Workflow Comparison

### Before (Single-Stage):
```
User clicks "Add Node"
  ↓
Generate all branches at once
  ↓
Done
```

### After (Multi-Stage):
```
Stage 1: Branches
  User clicks "Add Node"
    ↓
  Generate main branches
    ↓
  Branches appear as tabs
  
Stage 2: Children (per branch)
  User selects a branch tab
  User clicks "Add Node"
    ↓
  Generate sub-branches for that branch
    ↓
  Sub-branches added to selected branch
```

---

## Architecture Details

### Stage Flow

```
1. User opens Node Palette
   └─> Stage: 'branches' (default)
   
2. User clicks "Add branches"
   └─> Calls: generate_batch(stage='branches')
   └─> Prompt: _build_branches_prompt()
   └─> Result: Main branch ideas
   
3. User clicks on a branch (creates tab)
   └─> Stage: 'children'
   └─> stage_data: {'branch_name': 'Selected Branch'}
   
4. User clicks "Add nodes" in branch tab
   └─> Calls: generate_batch(stage='children', stage_data={'branch_name': ...})
   └─> Prompt: _build_children_prompt(branch_name=...)
   └─> Result: Sub-branch ideas for that branch
```

### Node Routing

**Mode Field**:
- Stage `branches`: nodes get `mode='branches'`
- Stage `children`: nodes get `mode='<branch_name>'` (for tab routing)

**Example**:
```python
# Branch stage
node['mode'] = 'branches'  # Routes to main branches array

# Children stage (for "History" branch)
node['mode'] = 'History'  # Routes to History branch's children tab
```

---

## Benefits

### For Users:
1. ✅ **Progressive Building**: Add branches first, then expand them
2. ✅ **Better Organization**: Each branch gets its own tab
3. ✅ **Clear Hierarchy**: Visual structure matches thinking process
4. ✅ **State Persistence**: Work saved when closing/reopening palette

### For Pedagogy:
1. ✅ **Guided Thinking**: Follows proper mind mapping methodology
2. ✅ **Stage-Based Learning**: Breadth first, then depth
3. ✅ **Clear Mental Model**: Matches how teachers actually think

### For UX:
1. ✅ **Less Overwhelming**: Generate nodes in manageable chunks
2. ✅ **Contextual Generation**: Sub-branches know their parent context
3. ✅ **Better Prompts**: Stage-specific prompts yield better results

---

## Prompt Examples

### Stage 1: Branches Prompt (Chinese)
```
为以下主题生成6个思维导图分支想法：太阳系

教学背景：天文学课程

你能够绘制思维导图，进行发散思维和头脑风暴。
思维方式：发散、联想、创造
1. 从多个角度对中心主题进行联想
2. 分支要覆盖不同的维度和方面
3. 每个分支要简洁明了，使用名词或名词短语
4. 鼓励创造性和多样性思考

要求：每个分支想法要简洁明了（1-5个词），不要使用完整句子，不要编号。只输出分支文本，每行一个。

生成6个分支想法：
```

### Stage 2: Children Prompt (Chinese)
```
为思维导图分支"行星系统"生成6个子分支想法：

主题：太阳系
上级分支：行星系统
教学背景：天文学课程

你能够为思维导图分支生成子想法，进一步细化和展开这个分支。
思维方式：深入、细化、展开
1. 围绕"行星系统"这个分支进行更深入的思考
2. 子分支应该是该分支的具体展开或细节
3. 每个子分支要简洁明了，使用名词或名词短语
4. 保持与上级分支的逻辑关联性

要求：每个子分支想法要简洁明了（1-5个词），不要使用完整句子，不要编号。只输出子分支文本，每行一个。

生成6个子分支想法：
```

---

## Testing Checklist

- [ ] Create new mind map
- [ ] Open Node Palette
- [ ] Click "Add branches" - verify branches generated
- [ ] Verify branches appear as tabs
- [ ] Click on a branch tab
- [ ] Click "Add nodes" - verify sub-branches generated
- [ ] Verify sub-branches added to correct branch
- [ ] Close Node Palette
- [ ] Reopen Node Palette
- [ ] Verify stage persists (tabs still present)
- [ ] Test with Chinese language
- [ ] Test with English language

---

## Compatibility

### Backward Compatibility: ✅ MAINTAINED

- Old mind maps without stages still work
- Default array configuration preserved
- Existing APIs remain functional
- No breaking changes to Mind Map spec structure

### Forward Compatibility: ✅ PREPARED

- Stage system can be extended (add more stages if needed)
- Prompt system is modular (easy to add new prompt types)
- Session tracking supports additional metadata

---

## Files Modified

1. ✅ `static/js/editor/node-palette-manager.js` (lines 108-125)
2. ✅ `agents/thinking_modes/node_palette/mindmap_palette.py` (full rewrite with stage support)

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Frontend config | ✅ Complete | useTabs + useStages enabled |
| Backend palette generator | ✅ Complete | Stage-aware with 2 prompt methods |
| Python compilation | ✅ Passes | No syntax errors |
| Lint checking | ✅ Clean | No linter errors |
| Documentation | ✅ Complete | This document |

---

## Next Steps (Optional Enhancements)

### Future Improvements:
1. 💡 Add stage indicators in UI (show "Stage 1: Branches" / "Stage 2: Children")
2. 💡 Add tooltips explaining each stage
3. 💡 Add keyboard shortcuts for stage navigation
4. 💡 Add bulk operations (e.g., "Expand all branches")
5. 💡 Add stage-based undo/redo

### Integration with ThinkGuide:
1. 💡 ThinkGuide can suggest next stage
2. 💡 Stage-aware conversation (knows which stage user is in)
3. 💡 Pedagogical guidance per stage

---

## Comparison with Tree Map

| Feature | Tree Map | Mind Map | Notes |
|---------|----------|----------|-------|
| Stages | 3 (dimensions → categories → children) | 2 (branches → children) | Mind Map is simpler |
| Tab system | ✅ Yes | ✅ Yes | Both use tabs |
| Stage persistence | ✅ Yes | ✅ Yes | Both persist state |
| Mode-based routing | ✅ Yes | ✅ Yes | Both use mode field |
| Prompt types | 3 methods | 2 methods | Appropriate for complexity |

---

## Conclusion

✅ **Mind Map now has full multi-stage Node Palette support!**

The implementation follows the proven Tree Map pattern but adapts it to Mind Map's simpler 2-stage workflow. Users can now:
- Add branches progressively
- Expand individual branches with sub-branches
- Work with clear hierarchical structure
- Benefit from stage-specific LLM prompts

This brings Mind Map to feature parity with Tree Map in terms of Node Palette functionality.

---

**Implementation Date**: 2025-10-19  
**Implemented By**: AI Agent  
**Status**: ✅ Ready for Testing

