# ThinkGuide Node Integration Test

This guide verifies that ThinkGuide can correctly read and modify nodes in Circle Maps.

## Prerequisites

1. Open a Circle Map in the editor (any template works)
2. Open browser console (F12)

## Test 1: Verify Node IDs

**Check what IDs are in the active diagram:**

```javascript
const container = document.querySelector('#d3-container');
const circles = container.querySelectorAll('circle[data-node-id]');
console.log('Node IDs in diagram:');
circles.forEach(c => {
    console.log(`- ${c.getAttribute('data-node-id')} (type: ${c.getAttribute('data-node-type')})`);
});
```

**Expected output:**
```
- outer_boundary (type: boundary)
- context_0 (type: context)
- context_1 (type: context)
- context_2 (type: context)
...
- center_topic (type: center)
```

## Test 2: Verify Data Normalization

**Check how ThinkGuide sees the diagram:**

```javascript
const thinkGuide = window.thinkingModeManager;
const diagramData = thinkGuide.extractDiagramData();
console.log('ThinkGuide diagram data:', diagramData);
```

**Expected output:**
```javascript
{
  center: { text: "Main Topic" },
  children: [
    { id: "context_0", text: "Item 1" },
    { id: "context_1", text: "Item 2" },
    ...
  ]
}
```

**✅ Verify:** Children have IDs matching the format `context_0`, `context_1`, etc.

## Test 3: Test Node Update

**Update a context node:**

```javascript
window.thinkingModeManager.updateDiagramNode('context_0', 'TEST UPDATE');
```

**Expected behavior:**
1. The first context node's text changes to "TEST UPDATE"
2. The diagram re-renders
3. The updated node **glows/pulses** (animation)

## Test 4: Test Center Update

**Update the center topic:**

```javascript
window.thinkingModeManager.updateCenterTopic('NEW TOPIC');
```

**Expected behavior:**
1. The center circle's text changes to "NEW TOPIC"
2. The diagram re-renders
3. The center node **glows/pulses** (animation)

## Test 5: Test Animation System

**Test individual node highlights:**

```javascript
// Highlight center
window.nodeIndicator.highlight('center', { 
    type: 'glow', 
    duration: 3000, 
    intensity: 8,
    color: '#FF0000'
});

// Highlight a context node
window.nodeIndicator.highlight('context_0', { 
    type: 'pulse', 
    duration: 2000,
    intensity: 6
});
```

**Expected behavior:**
- Center node glows red
- context_0 node pulses
- Animations are clearly visible

## Test 6: End-to-End ThinkGuide Test

**Open ThinkGuide and try changing a node:**

1. Click the "ThinkGuide" button
2. Send a message: "Change the first node to 'Hello World'"
3. Wait for ThinkGuide to respond

**Expected behavior:**
1. ThinkGuide acknowledges the change
2. The first context node updates to "Hello World"
3. The node **highlights with animation**
4. ThinkGuide confirms the update

## Troubleshooting

### Issue: Node doesn't update

**Check:**
```javascript
const editor = window.currentEditor;
console.log('Editor spec:', editor?.currentSpec);
console.log('Context array:', editor?.currentSpec?.context);
```

If `context` is undefined, the spec structure is unexpected.

### Issue: Animation doesn't show

**Check:**
```javascript
console.log('NodeIndicator loaded?', !!window.nodeIndicator);
console.log('Nodes in active editor:', 
    document.querySelectorAll('#d3-container [data-node-id]').length);
```

If 0 nodes found, you're not in the active editor.

### Issue: Wrong node updates

**Check IDs match:**
```javascript
// What ThinkGuide sends
const diagramData = window.thinkingModeManager.extractDiagramData();
console.log('ThinkGuide IDs:', diagramData.children.map(c => c.id));

// What renderer created
const renderedIds = Array.from(
    document.querySelectorAll('#d3-container [data-node-id]')
).map(el => el.getAttribute('data-node-id'));
console.log('Rendered IDs:', renderedIds);
```

IDs should match exactly.

---

## Summary Checklist

- [ ] Node IDs follow `context_0`, `context_1`, `center_topic` format
- [ ] ThinkGuide normalizes data correctly
- [ ] `updateDiagramNode()` updates the correct node
- [ ] `updateCenterTopic()` updates the center
- [ ] Animations trigger after updates
- [ ] End-to-end ThinkGuide conversation works

If all tests pass, **ThinkGuide is fully integrated with node animations!** 🎉

---

**Last Updated**: October 10, 2025  
**Author**: MindSpring Team (lycosa9527)

