# Node Palette Testing Guide
**Feature:** Multi-LLM Node Brainstorming for Circle Maps  
**Author:** lycosa9527  
**Made by:** MindSpring Team

## Overview

This guide provides comprehensive testing procedures for the Node Palette feature, which allows users to brainstorm Circle Map nodes using 4 LLMs (qwen, deepseek, hunyuan, kimi) with round-robin rotation.

## Quick Start Test

1. **Start the server:**
   ```bash
   python run_server.py
   ```

2. **Open editor:** Navigate to `http://localhost:8000/editor`

3. **Create a Circle Map:**
   - Select "Circle Map" from diagram selector
   - Enter a topic (e.g., "Photosynthesis")
   - Click "Generate"

4. **Open ThinkGuide:**
   - Click the "ThinkGuide" button in toolbar
   - Enter context information (grade level, subject, etc.)

5. **Trigger Node Palette:**
   - In ThinkGuide chat, type one of:
     - English: "show me node palette"
     - English: "brainstorm more ideas"
     - Chinese: "给我节点选择板"
     - Chinese: "头脑风暴更多想法"

6. **Expected behavior:**
   - Circle Map fades out
   - Node Palette panel fades in
   - First batch (20 nodes) loads from qwen
   - Nodes appear in 4-column masonry grid
   - Selection counter shows "Selected: 0/20"

## Detailed Test Cases

### Test 1: Node Generation
**Goal:** Verify multi-LLM node generation with round-robin rotation

**Steps:**
1. Trigger Node Palette as described above
2. Observe console logs for batch loading
3. Scroll down when batch completes
4. Verify next batch loads from different LLM

**Expected Results:**
- ✅ Batch 1: qwen generates ~20 nodes
- ✅ Batch 2: deepseek generates ~20 nodes
- ✅ Batch 3: hunyuan generates ~20 nodes
- ✅ Batch 4: kimi generates ~20 nodes
- ✅ Pattern repeats (qwen → deepseek → hunyuan → kimi)

**Console Logs to Check:**
```
[NodePalette] Starting | Topic: "Photosynthesis" | Existing nodes: 3
[NodePalette] Batch 1: qwen generating...
[NodePalette] Node #1: "Chlorophyll pigments" (qwen)
[NodePalette] Batch 1 complete (2.34s) | LLM: qwen | Unique: 18 | Duplicates: 2 | Total: 18
```

### Test 2: Real-Time Deduplication
**Goal:** Verify exact and fuzzy duplicate detection

**Steps:**
1. Load multiple batches (at least 3)
2. Observe "Duplicates: X" count in console logs
3. Check that similar nodes are filtered

**Expected Results:**
- ✅ Exact duplicates are filtered (100% match)
- ✅ Fuzzy duplicates are filtered (>85% similarity)
- ✅ Deduplication rate shown in console logs
- ✅ Unique nodes count increases correctly

**Console Example:**
```
[NodePalette] Batch 2 complete (3.12s) | LLM: deepseek | Unique: 16 | Duplicates: 4 | Total: 34 | Dedup rate: 20.0%
[NodePalette] Duplicate fuzzy (0.92): "Green leaf pigments"
```

### Test 3: Node Selection & Animations
**Goal:** Verify selection UI and animations

**Steps:**
1. Click on a node card
2. Observe selection animations
3. Click again to deselect
4. Select multiple nodes (5+)

**Expected Results:**
- ✅ Card enlarges (scale 1.05x)
- ✅ Border turns blue (#4a90e2) and thickens
- ✅ Checkmark appears with bounce animation
- ✅ Card glows with pulse animation
- ✅ Selection counter updates: "Selected: 5/34"
- ✅ Finish button enables and shows count

**CSS Animations:**
- Scale transition: 0.2s ease
- Checkmark bounce: 0.4s cubic-bezier
- Glow pulse: 2s infinite ease-in-out

### Test 4: Selection Logging
**Goal:** Verify backend logging of selections

**Steps:**
1. Select 5 nodes
2. Check backend console
3. Deselect 2 nodes
4. Check backend console again

**Expected Backend Logs:**
```
[NodePalette-Selection] User selected node | Session: palette_a | Node: 'Chlorophyll pigments' | ID: palette_abc123_qwen_1_5
[NodePalette-Selection] User selected node | Session: palette_a | Node: 'Sunlight energy' | ID: palette_abc123_qwen_1_12
...
[NodePalette-Selection] User deselected node | Session: palette_a | Node: 'Water molecules' | ID: palette_abc123_deepseek_2_3
```

### Test 5: Infinite Scroll
**Goal:** Verify automatic batch loading on scroll

**Steps:**
1. Start Node Palette
2. Scroll to bottom of container
3. Wait for next batch to load
4. Repeat until reaching 12 batches

**Expected Results:**
- ✅ Batch loads when 200px from bottom
- ✅ Loading indicator shows briefly
- ✅ New nodes append smoothly
- ✅ No duplicate batch requests (isLoading flag works)

**Console Example:**
```
[NodePalette] User scrolled near bottom, loading next batch
[NodePalette] Loading batch #5
[NodePalette] Batch 5: qwen generating...
```

### Test 6: Smart Stopping Conditions
**Goal:** Verify generation stops at limits

**Steps:**
1. Keep scrolling until one limit is reached
2. Verify end message appears

**Expected Results:**
- ✅ Stops after 200 total nodes OR
- ✅ Stops after 12 batches (3 rounds × 4 LLMs)
- ✅ End message shows: "✓ Generated X nodes from Y batches"
- ✅ "Select your favorites and click Finish" message
- ✅ No more batch requests after limit

**Console Example:**
```
[NodePalette] Reached limit: nodes=200, batches=10
[NodePalette] End message displayed
```

### Test 7: Finish & Circle Map Integration
**Goal:** Verify selected nodes are added to Circle Map

**Steps:**
1. Select 5-10 nodes from Node Palette
2. Click "Finish" button
3. Observe transition and node assembly

**Expected Results:**
- ✅ Backend logs finish event with metrics
- ✅ Node Palette fades out
- ✅ Circle Map fades in
- ✅ Custom event `nodePaletteComplete` is dispatched
- ✅ Selected nodes are added to Circle Map

**Backend Logs:**
```
[NodePalette-Finish] User completed session | Session: palette_a
[NodePalette-Finish]   Selected: 7/69 nodes | Batches: 4 | Selection rate: 10.1%
[NodePalette] Session ended: palette_a | Reason: user_finished
[NodePalette]   Duration: 45.23s | Batches: 4 | Total nodes: 69 | Avg nodes/batch: 17.2
[NodePalette]   qwen: 2/2 calls (100% success, 2.34s avg)
[NodePalette]   deepseek: 1/1 calls (100% success, 3.12s avg)
[NodePalette] Session cleanup complete: palette_a
```

**Frontend Logs:**
```
[NodePalette-Finish] User finishing | Selected: 7/69 | Batches: 4 | Selection rate: 10.1%
[NodePalette-Finish] Selected nodes: ['Chlorophyll pigments', 'Sunlight energy', ...]
[NodePalette] Dispatched nodePaletteComplete event with 7 nodes
[NodePalette-Finish] Node Palette complete, nodes added to Circle Map
```

### Test 8: Error Handling
**Goal:** Verify graceful error handling

**Test 8a: LLM Timeout**
1. Simulate slow network (browser DevTools → Network → Throttling)
2. Trigger Node Palette
3. Observe timeout handling

**Expected:**
- ✅ Error event yielded: `{event: 'error', message: '...', fallback: '...'}`
- ✅ Batch marked as failed in console
- ✅ Next LLM called on next scroll
- ✅ Session continues normally

**Test 8b: Zero Selection**
1. Click Finish without selecting any nodes
2. Verify alert appears

**Expected:**
- ✅ Alert: "Please select at least one node"
- ✅ Node Palette remains open
- ✅ No Circle Map transition

**Test 8c: Network Interruption**
1. Start batch loading
2. Disconnect network
3. Reconnect and scroll

**Expected:**
- ✅ Error logged to console
- ✅ Next batch attempts on scroll
- ✅ No UI freeze or crash

### Test 9: Multi-Language Support
**Goal:** Verify Chinese and English support

**Test 9a: Chinese**
```
User: "给我节点选择板"
ThinkGuide: "用户想要打开节点选择板，为「光合作用」头脑风暴更多观察点..."
ThinkGuide: "节点选择板已准备就绪！从多个AI生成的节点中选择您喜欢的..."
```

**Test 9b: English**
```
User: "show me node palette"
ThinkGuide: "User wants to open Node Palette to brainstorm more observations for 'Photosynthesis'..."
ThinkGuide: "Node Palette is ready! Select your favorite nodes from multiple AI-generated suggestions..."
```

### Test 10: Debug Endpoint
**Goal:** Verify debug endpoint for troubleshooting

**Steps:**
1. Start Node Palette (note session ID in console)
2. Open new browser tab
3. Navigate to: `http://localhost:8000/thinking_mode/node_palette/debug/{session_id}`

**Expected JSON Response:**
```json
{
  "session_id": "palette_abc123",
  "session_exists": true,
  "total_nodes_generated": 69,
  "unique_texts_count": 69,
  "total_batches": 4,
  "batch_counters": {
    "qwen": 2,
    "deepseek": 1,
    "hunyuan": 1
  },
  "current_llm_index": 4,
  "next_llm": "qwen",
  "nodes_by_llm": {
    "qwen": 36,
    "deepseek": 18,
    "hunyuan": 15
  },
  "llm_metrics": {
    "qwen": {
      "calls": 2,
      "successes": 2,
      "failures": 0,
      "total_time": 4.68
    }
  },
  "sample_nodes": [...],
  "sample_seen_texts": [...]
}
```

## Performance Benchmarks

### Target Performance
- **First batch latency:** < 5 seconds
- **Deduplication overhead:** < 50ms per node
- **Selection response:** < 100ms
- **Scroll smoothness:** 60 FPS
- **Total session duration:** 30-120 seconds (typical)

### Monitoring
Check these metrics in console logs:
```
[NodePalette] Batch 1 complete (2.34s) | ...  ← Batch latency
[NodePalette] qwen: 2/2 calls (100% success, 2.34s avg)  ← LLM performance
[NodePalette]   Duration: 45.23s | Batches: 4 | ...  ← Session duration
```

## Common Issues & Troubleshooting

### Issue 1: Nodes Not Loading
**Symptoms:** First batch never appears, spinner indefinite

**Checks:**
1. Backend console for errors
2. Network tab for failed requests
3. LLM service availability
4. Session ID logged correctly

### Issue 2: Selection Not Working
**Symptoms:** Clicking nodes has no effect

**Checks:**
1. Check `window.nodePaletteManager` exists
2. Verify Finish button listener attached
3. Check CSS classes applying correctly
4. Browser console for JS errors

### Issue 3: Duplicate Nodes Appearing
**Symptoms:** Seeing identical or very similar nodes

**Checks:**
1. Check deduplication logs in backend
2. Verify `_deduplicate_node_streaming` is called
3. Check similarity threshold (should be 0.85)
4. Ensure `seen_texts` set is populated

### Issue 4: Finish Button Disabled
**Symptoms:** Button stays grayed out even with selections

**Checks:**
1. Verify `selectedNodes` Set is populated
2. Check `updateSelectionCounter()` is called
3. Verify button ID matches: `finish-selection-btn`
4. Check console for selection logs

## Regression Testing Checklist

Before each release, verify:

- [ ] ThinkGuide still works normally for Circle Maps
- [ ] Regular node generation (add_nodes action) still works
- [ ] Circle Map rendering unaffected
- [ ] Other diagram types (Bubble Map, etc.) unaffected
- [ ] Learning Mode unaffected
- [ ] No memory leaks (check DevTools → Memory)
- [ ] Mobile responsive (test on tablet/phone viewport)
- [ ] Dark mode styling correct

## Success Criteria

✅ **All 10 test cases pass**  
✅ **No linter errors**  
✅ **No console errors in browser or backend**  
✅ **Performance within benchmarks**  
✅ **Comprehensive logging visible**  
✅ **Session cleanup verified**

## Next Steps

After passing all tests:
1. User acceptance testing (UAT)
2. Performance optimization if needed
3. Documentation updates
4. Feature announcement to users
5. Monitor production logs for issues

---

**Last Updated:** October 11, 2025  
**Implementation Status:** ✅ Complete  
**Lines of Code:** ~2,500 across 9 files

