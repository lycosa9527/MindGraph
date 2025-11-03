# Node Text Wrapping Implementation Review

## Executive Summary

This document reviews the current state of text wrapping and node width calculation across all diagram renderers in MindGraph, and proposes a solution to implement automatic text wrapping by constraining node width instead of expanding nodes to accommodate long text.

## Current State Analysis

### 1. **Concept Map Renderer** ✅ (Has Wrapping)
- **Location**: `static/js/renderers/concept-map-renderer.js`
- **Current Implementation**:
  - Uses `wrapIntoLines()` function with fixed `maxTextWidth` (350px for topic, 300px for concept)
    ```149:164:static/js/renderers/concept-map-renderer.js
    function wrapIntoLines(text, fontSize, maxWidth) {
        const words = String(text).split(/\s+/);
        const lines = [];
        let current = '';
        for (const w of words) {
            const candidate = current ? current + ' ' + w : w;
            if (measureLineWidth(candidate, fontSize) <= maxWidth || current === '') {
                current = candidate;
            } else {
                lines.push(current);
                current = w;
            }
        }
        if (current) lines.push(current);
        return lines;
    }
    ```
  - Calculates box width AFTER wrapping based on longest line (lines 169-175)
    ```166:175:static/js/renderers/concept-map-renderer.js
    function drawBox(x, y, text, isTopic = false) {
        const fontSize = isTopic ? THEME.fontTopic : THEME.fontConcept;
        const maxTextWidth = isTopic ? 350 : 300;
        const lines = wrapIntoLines(text, fontSize, maxTextWidth);
        const lineHeight = Math.round(fontSize * 1.2);
        const textWidth = Math.max(...lines.map(l => measureLineWidth(l, fontSize)), 20);
        const paddingX = 16;
        const paddingY = 10;
        const boxW = Math.ceil(textWidth + paddingX * 2);
        const boxH = Math.ceil(lines.length * lineHeight + paddingY * 2);
    ```
  - Renders multi-line text using `<tspan>` elements (lines 197-199)
    ```197:199:static/js/renderers/concept-map-renderer.js
    lines.forEach((ln, i) => {
        textEl.append('tspan').attr('x', x).attr('dy', i === 0 ? 0 : lineHeight).text(ln);
    });
    ```
- **Status**: **Already implements the desired behavior** - This is the reference implementation

### 2. **Flow Map Renderer** ❌ (No Wrapping)
- **Location**: `static/js/renderers/flow-renderer.js`
- **Current Implementation**:
  - Uses `measureTextSize()` to measure entire text width (lines 63-73)
    ```63:73:static/js/renderers/flow-renderer.js
    function measureTextSize(text, fontSize) {
        const t = tempSvg.append('text')
            .attr('x', -9999)
            .attr('y', -9999)
            .attr('font-size', fontSize)
            .attr('dominant-baseline', 'hanging')
            .text(text || '');
        const bbox = t.node().getBBox();
        t.remove();
        return { w: Math.ceil(bbox.width), h: Math.ceil(bbox.height || fontSize) };
    }
    ```
  - Node width calculation (line 88): `const w = Math.max(100, m.w + hPad * 2);` where `m.w` is full text width
  - Text rendering (line 216): Uses single `.text(n.text)` with no wrapping
    ```209:216:static/js/renderers/flow-renderer.js
    svg.append('text')
        .attr('x', n.x)
        .attr('y', n.y)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', textColor || '#fff')
        .attr('font-size', THEME.fontNode)
        .text(n.text);
    ```
- **Issues**:
  - Long text creates very wide nodes
  - No max width constraint
  - Text displayed as single line (may overflow visually)

### 3. **Brace Map Renderer** ❌ (No Wrapping)
- **Location**: `static/js/renderers/brace-renderer.js`
- **Current Implementation**:
  - Uses `measureTextWidth()` for text width calculation (lines 129-146)
    ```129:146:static/js/renderers/brace-renderer.js
    function measureTextWidth(text, fontSpec, fontWeight = 'normal') {
        const { size, family } = parseFontSpec(fontSpec);
        // Create a temporary hidden SVG for measurement
        const tempSvg = d3.select('#d3-container')
            .append('svg')
            .attr('width', 0)
            .attr('height', 0)
            .style('position', 'absolute')
            .style('visibility', 'hidden');
        const tempText = tempSvg.append('text')
            .text(text || '')
            .attr('font-size', size)
            .attr('font-family', family)
            .style('font-weight', fontWeight);
        const bbox = tempText.node().getBBox();
        tempSvg.remove();
        return Math.max(0, bbox?.width || 0);
    }
    ```
  - Node width calculation (line 328): `Math.max(maxPartWidth, measureTextWidth(...)) + partPadding * 2`
  - Text rendering (line 366): Uses single `.text(part.name || '')` with no wrapping
    ```353:366:static/js/renderers/brace-renderer.js
    svg.append('text')
        .attr('x', partsStartX + partBoxWidth / 2)
        .attr('y', partY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.partText)
        .attr('font-size', parseFontSpec(THEME.fontPart).size)
        .attr('font-family', parseFontSpec(THEME.fontPart).family)
        .attr('font-weight', 'bold')
        .attr('data-node-id', `brace-part-${partIndex}`)
        .attr('data-node-type', 'part')
        .attr('data-part-index', partIndex)
        .attr('data-text-for', `part_${partIndex}`)
        .text(part.name || '');
    ```
- **Issues**:
  - Wide nodes for long text
  - No max width limits
  - Potential layout overflow

### 4. **Mind Map Renderer** ⚠️ (Partial - Depends on Python Agent)
- **Location**: `static/js/renderers/mind-map-renderer.js`
- **Current Implementation**:
  - Uses `pos.width` and `pos.height` from Python agent layout (lines 189-190, 234-235)
    ```189:190:static/js/renderers/mind-map-renderer.js
    const branchWidth = pos.width || (pos.text ? Math.max(100, pos.text.length * 10) : 100);
    const branchHeight = pos.height || 50;
    ```
  - Fallback: `Math.max(100, pos.text.length * 10)` for width estimation (character-based, not actual measurement)
  - Text rendering (line 227): Uses single `.text(pos.text || 'Branch')` with no wrapping
    ```217:227:static/js/renderers/mind-map-renderer.js
    svg.append('text')
        .attr('x', branchX)
        .attr('y', branchY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', finalBranchTextColor)
        .attr('font-size', THEME.fontBranch || '16px')
        .attr('data-text-for', branchNodeId)
        .attr('data-node-id', branchNodeId)
        .attr('data-node-type', 'branch')
        .text(pos.text || 'Branch');
    ```
- **Issues**:
  - Width comes from Python agent, no client-side wrapping verification
  - Fallback calculation doesn't account for wrapping or actual font metrics
  - Text displayed as single line (no tspan wrapping)

### 5. **Tree Map Renderer** ❌ (No Wrapping)
- **Location**: `static/js/renderers/tree-renderer.js`
- **Current Implementation**:
  - Uses `measureSvgTextBox()` which measures full text width (lines 104-127)
    ```104:127:static/js/renderers/tree-renderer.js
    function measureSvgTextBox(svg, text, fontPx, hPad = 14, vPad = 10) {
        try {
            const temp = svg.append('text')
                .attr('x', -10000)
                .attr('y', -10000)
                .attr('font-size', fontPx)
                .attr('font-family', 'Inter, Segoe UI, sans-serif')
                .attr('visibility', 'hidden')
                .text(text || '');
            const node = temp.node();
            let textWidth = 0;
            if (node && node.getComputedTextLength) {
                textWidth = node.getComputedTextLength();
            } else if (node && node.getBBox) {
                textWidth = node.getBBox().width || 0;
            }
            temp.remove();
            const textHeight = Math.max(1, fontPx * 1.2);
            return { w: Math.ceil(textWidth + hPad * 2), h: Math.ceil(textHeight + vPad * 2) };
        } catch (e) {
            // Fallback to approximation if DOM measurement fails
            return measureTextApprox(text, fontPx, hPad, vPad);
        }
    }
    ```
  - Box width = `textWidth + padding * 2` (line 122)
  - No wrapping - measures entire text as one line
- **Issues**:
  - Wide nodes for long text
  - Column widths calculated from full text width (line 148)
  - No text wrapping logic

### 6. **Bubble/Double Bubble Map Renderers** ❌ (No Wrapping)
- **Location**: `static/js/renderers/bubble-map-renderer.js`
- **Current Implementation**:
  - Similar to other renderers - measures full text width
  - No wrapping logic implemented
- **Issues**: Same as above renderers

### 7. **Shared Utilities** ✅ (Has Wrapping Function)
- **Location**: `static/js/renderers/shared-utilities.js`
- **Function**: `wrapText(text, width)` (lines 244-275)
    ```244:275:static/js/renderers/shared-utilities.js
    function wrapText(text, width) {
        text.each(function() {
            const textElement = d3.select(this);
            const words = textElement.text().split(/\s+/).reverse();
            let word;
            let line = [];
            let lineNumber = 0;
            const lineHeight = 1.1; // ems
            const y = textElement.attr("y");
            const dy = parseFloat(textElement.attr("dy")) || 0;
            
            let tspan = textElement.text(null).append("tspan")
                .attr("x", 0)
                .attr("y", y)
                .attr("dy", dy + "em");
                
            while (word = words.pop()) {
                line.push(word);
                tspan.text(line.join(" "));
                if (tspan.node().getComputedTextLength() > width) {
                    line.pop();
                    tspan.text(line.join(" "));
                    line = [word];
                    tspan = textElement.append("tspan")
                        .attr("x", 0)
                        .attr("y", y)
                        .attr("dy", ++lineNumber * lineHeight + dy + "em")
                        .text(word);
                }
            }
        });
    }
    ```
- **Current Usage**: Limited - mainly for learning sheet mode
- **Note**: This function operates on existing D3 text elements, whereas Concept Map uses a word-splitting approach before rendering
- **Potential**: Can be adapted/reused across all renderers

## Text Update Behavior

### Current Update Flow
When users edit nodes via `NodeEditor`:
1. `interactive-editor.js` → `updateNodeText()` → diagram-specific update method
2. Each update method modifies the spec and calls `renderDiagram()`
3. `renderDiagram()` re-renders the entire diagram
4. **Problem**: Re-rendering uses the same non-wrapping logic, so wide nodes persist

### Node Editor
- **Location**: `static/js/editor/node-editor.js`
- **Current**: Simple textarea, no width preview
- **Enhancement Opportunity**: Could show preview of how text will wrap

## Problems Identified

### 1. **Inconsistent Behavior**
- Concept maps wrap text automatically
- All other diagram types don't wrap
- User experience inconsistency across diagram types

### 2. **Node Width Issues**
- Long text creates extremely wide nodes
- Breaks layout aesthetics
- Causes horizontal scrolling or overflow
- Makes diagrams harder to read and navigate

### 3. **No Standardized Approach**
- Each renderer implements text measurement differently
- No shared wrapping logic (despite `wrapText()` existing)
- Different padding/spacing calculations

### 4. **Re-rendering Doesn't Fix Width**
- When users edit text, nodes stay wide if long
- No automatic width adjustment after editing

## Proposed Solution

### Phase 1: Create Unified Text Wrapping Utility

**Approach**: Enhance `shared-utilities.js` with a comprehensive text wrapping function

```javascript
/**
 * Measure and wrap text with maximum width constraint
 * @param {string} text - Text to wrap
 * @param {number} fontSize - Font size in pixels
 * @param {number} maxWidth - Maximum text width before wrapping
 * @param {SVG} svg - SVG element for measurement
 * @returns {Object} { lines: string[], textWidth: number, textHeight: number }
 */
function measureAndWrapText(text, fontSize, maxWidth, svg) {
    // Implementation similar to concept-map-renderer.js wrapIntoLines()
    // Returns wrapped lines and dimensions
}
```

**Benefits**:
- Single source of truth for text wrapping
- Consistent behavior across all renderers
- Easier to maintain and update

### Phase 2: Update Each Renderer

**Strategy**: Add max width constraints to each renderer

#### For Each Renderer:
1. **Define Max Widths**: Set reasonable max widths per node type
   - Topics: 300-350px
   - Regular nodes: 250-300px
   - Small nodes: 150-200px

2. **Measure with Wrapping**: Use `measureAndWrapText()` instead of measuring full text

3. **Calculate Node Dimensions**: 
   - Width = `min(maxTextWidth, longestLineWidth) + padding * 2`
   - Height = `(lines.length * lineHeight) + padding * 2`

4. **Render Multi-line Text**: Use `<tspan>` elements for each line (like concept map)

#### Specific Renderer Changes:

**Flow Renderer**:
- Current: `const w = Math.max(100, m.w + hPad * 2);` where `hPad = 14` (line 80)
- Change: Add max width (e.g., 280px), wrap text, calculate width from wrapped lines
- Padding: `hPad = 14`, `vPad = 10` (lines 80-81)

**Brace Renderer**:
- Current: `Math.max(maxPartWidth, measureTextWidth(...)) + partPadding * 2` where `partPadding = 12` (line 225)
- Change: Wrap at max width (topic: 320px, part: 280px, subpart: 240px), measure wrapped lines
- Padding: `topicPadding = 16`, `partPadding = 12`, `subpartPadding = 8` (lines 224-226)

**Tree Renderer**:
- Current: `measureSvgTextBox()` measures full width
- Change: Add wrapping before measurement, update `measureSvgTextBox()` to accept maxWidth

**Mind Map Renderer**:
- Current: Uses Python-provided dimensions
- Change: Add client-side wrapping check, override if Python provides very wide nodes

**Bubble Map Renderers**:
- Current: Measures full text width
- Change: Apply wrapping with max width constraints

### Phase 3: Update Text Editing

**Enhance `updateNodeText()` methods**:
- When text is updated, ensure wrapping is applied
- Re-calculate node dimensions based on wrapped text
- Preserve node position, adjust size only

### Phase 4: Handle Existing Wide Nodes

**Migration Strategy**:
- When loading existing diagrams with wide nodes, automatically wrap text
- Preserve layout as much as possible
- Optionally add a "compact mode" to re-wrap all nodes

## Implementation Considerations

### 1. **Max Width Values**
Need to define per diagram type and node type:
- **Concept Map**: Topic 350px, Concept 300px ✅ (already set)
- **Flow Map**: Step 280px (recommended)
- **Brace Map**: Topic 320px, Part 280px, Subpart 240px
- **Mind Map**: Topic 300px, Branch 250px, Child 200px
- **Tree Map**: Root 320px, Branch 280px, Leaf 240px
- **Bubble Maps**: Center 300px, Attribute 250px

### 2. **Text Measurement**
- Use SVG `getBBox()` or `getComputedTextLength()` for accuracy
- Create temporary hidden text elements for measurement
- Cache measurements when possible for performance

### 3. **Line Height & Padding**
- Standardize line height: `fontSize * 1.2` (matches Concept Map line 170)
- Current padding values in codebase:
  - Flow Map: `hPad = 14`, `vPad = 10` (lines 80-81)
  - Brace Map: `topicPadding = 16`, `partPadding = 12`, `subpartPadding = 8` (lines 224-226)
  - Concept Map: `paddingX = 16`, `paddingY = 10` (lines 172-173)
  - Tree Map: defaults `hPad = 14`, `vPad = 10` (line 104)
- Recommendation: Maintain existing padding per renderer for consistency

### 4. **Performance**
- Wrapping adds computation, but minimal impact for typical node counts
- Measurement caching can help
- Consider lazy wrapping for very large diagrams

### 5. **Backward Compatibility**
- Existing diagrams should work after update
- Wide nodes will be automatically wrapped on next edit/render
- No data migration needed

### 6. **Edge Cases**
- Very long single words (hyphenate or allow overflow?)
- Empty text (maintain minimum node size)
- Special characters/Unicode (handle in measurement)
- Mixed font sizes (use actual font size for measurement)

## Code Structure Recommendations

### Centralized Utilities
```javascript
// shared-utilities.js additions
const TEXT_WRAPPING_CONFIG = {
    concept_map: { topic: 350, concept: 300 },
    flow_map: { step: 280 },
    brace_map: { topic: 320, part: 280, subpart: 240 },
    mindmap: { topic: 300, branch: 250, child: 200 },
    tree_map: { root: 320, branch: 280, leaf: 240 },
    bubble_map: { center: 300, attribute: 250 }
};

function measureAndWrapText(text, fontSize, maxWidth, svg) { ... }
function getMaxTextWidth(diagramType, nodeType) { ... }
```

### Renderer Pattern
```javascript
// Example for flow-renderer.js
function renderFlowchart(spec, theme, dimensions) {
    // ... existing code ...
    
    const nodes = spec.steps.map(step => {
        const txt = step.text || '';
        const maxWidth = TEXT_WRAPPING_CONFIG.flow_map.step;
        const wrapped = measureAndWrapText(txt, THEME.fontNode, maxWidth, tempSvg);
        
        const w = Math.max(100, wrapped.textWidth + hPad * 2);
        const h = Math.max(40, wrapped.textHeight + vPad * 2);
        
        return { step, text: txt, wrapped, w, h };
    });
    
    // ... render with wrapped text using tspan elements ...
}
```

## Benefits of This Approach

1. **Consistent UX**: All diagrams wrap text the same way
2. **Better Aesthetics**: Nodes stay reasonably sized
3. **Improved Readability**: Multi-line text is easier to read than very wide single lines
4. **Layout Stability**: Prevents horizontal overflow issues
5. **Maintainability**: Centralized logic, easier to update
6. **User Control**: Users can still use Ctrl+Enter for manual line breaks

## Potential Challenges

1. **Layout Recalculation**: Wrapped text may affect overall diagram layout
   - Solution: Re-calculate positions if needed, maintain relative positioning

2. **Python Agent Coordination**: Mind maps use Python agent for layout
   - Solution: Add JavaScript-side wrapping check, override if too wide

3. **Performance**: More text measurements for wrapping
   - Solution: Cache measurements, optimize for typical cases

4. **Visual Consistency**: Some nodes may look different after wrapping
   - Solution: Use consistent max widths, maintain padding standards

5. **Existing Wide Nodes**: Users may have created diagrams expecting wide nodes
   - Solution: Wrap automatically on next render/edit, maintain positions

## Testing Checklist

- [ ] Test each diagram type with long text
- [ ] Verify wrapping at max width boundaries
- [ ] Test text editing updates wrapping correctly
- [ ] Verify node positioning remains stable
- [ ] Test with very long single words
- [ ] Test with empty text
- [ ] Test with special characters/Unicode
- [ ] Performance test with many nodes
- [ ] Test backward compatibility with existing diagrams

## Recommendations

### Priority 1 (High Impact, Medium Effort)
1. ✅ Implement unified wrapping utility in `shared-utilities.js`
2. ✅ Update Flow Map renderer (most commonly used)
3. ✅ Update Brace Map renderer (currently has wide node issues)
4. ✅ Update Tree Map renderer

### Priority 2 (Medium Impact, Medium Effort)
5. ✅ Update Bubble/Double Bubble Map renderers
6. ✅ Update Mind Map renderer (coordinate with Python agent)

### Priority 3 (Polish)
7. ✅ Enhance Node Editor with wrapping preview
8. ✅ Add max width configuration options
9. ✅ Optimize performance with caching

## Conclusion

The current implementation is inconsistent - only Concept Maps have automatic text wrapping. Implementing a unified wrapping system will:
- Improve user experience across all diagram types
- Prevent nodes from becoming too wide
- Make diagrams more readable and visually appealing
- Provide consistency that users expect

The solution is feasible with moderate effort and can be implemented incrementally per renderer. The existing `wrapText()` function and Concept Map implementation provide good reference points.

---

**Review Date**: 2024-11-02  
**Reviewed By**: AI Assistant  
**Status**: Ready for Implementation

