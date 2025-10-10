# Node ID Standards for MindGraph

This document defines the standard `data-node-id` and `data-node-type` conventions for all diagram types.

## Circle Map

### Node IDs
- **Center Topic**: `center_topic`
  - `data-node-type="center"`
  - The main concept/topic at the center
  
- **Context Nodes**: `context_0`, `context_1`, `context_2`, ...
  - `data-node-type="context"`
  - Observations or related concepts surrounding the center
  
- **Outer Boundary**: `outer_boundary`
  - `data-node-type="boundary"`
  - The large circle that frames the diagram (visual only, not interactive)

### Usage in ThinkGuide
```javascript
// Highlight the center
window.nodeIndicator.highlight('center_topic', options);
// or use alias
window.nodeIndicator.highlight('center', options);

// Highlight a context node
window.nodeIndicator.highlight('context_0', options);
```

## Standard Aliases

The NodeIndicator system supports these aliases for compatibility:

- **`'center'`**: Finds nodes with:
  1. `data-node-type="center"` (preferred)
  2. `data-node-type="topic"` (legacy)
  3. `data-node-id="center_topic"`
  4. `data-node-id="topic_center"` (legacy)
  5. Largest circle (fallback for old templates)

## Benefits

1. **Consistent**: All new diagrams use the same ID pattern
2. **Predictable**: ThinkGuide can reliably target specific nodes
3. **Compatible**: Fallback logic handles old diagrams
4. **Future-proof**: Easy to extend for new diagram types

## Migration Notes

Old templates may have:
- Random IDs like `node_78`, `node_0`, etc.
- Missing `data-node-type` attributes
- Different ID schemes

The NodeIndicator system handles these gracefully with fallback logic, but new diagrams should use the standard IDs defined above.

---

**Last Updated**: October 10, 2025  
**Author**: MindSpring Team (lycosa9527)

