# 🧪 Concurrent Token Streaming Testing Guide

**Author:** lycosa9527  
**Team:** MindSpring Team  
**Date:** October 13, 2025

---

## ✅ Implementation Status

### **Completed Phases (1-5):**
- ✅ **Phase 1:** Pre-implementation (backup, branch, cache clear)
- ✅ **Phase 2:** Middleware `stream_progressive()` added
- ✅ **Phase 3:** Generator V2 updated to use middleware
- ✅ **Phase 4:** All components verified (router, frontend, prompts)
- ✅ **Phase 5:** Syntax checks & imports passing
- 🟢 **Server:** Running on port **9527**

---

## 🎯 Manual Testing Steps

### **Step 1: Open Application**
```
http://localhost:9527
```

### **Step 2: Create Circle Map**
1. Click "New Circle Map" or select existing one
2. Add center topic: **"汽车"** (Cars) or any topic
3. Add 2-3 initial nodes (optional)

### **Step 3: Open ThinkGuide**
1. Click ThinkGuide button (chat icon)
2. Verify ThinkGuide opens
3. Initial greeting should appear

### **Step 4: Open Node Palette** 🚀
1. Click **"Node Palette"** button in ThinkGuide
2. Modal should open immediately

### **Step 5: Observe Concurrent Streaming** ⭐

**🔍 What to Watch For:**

#### **Browser Console (F12):**
```
[NodePalette] Batch 1 starting: 4 LLMs firing concurrently
[NodePalette] Node #1: "四个轮子" (qwen)
[NodePalette] Node #2: "Transportation" (deepseek)
[NodePalette] Node #3: "速度快" (hunyuan)
[NodePalette] qwen complete: 12 unique, 3 duplicates (2.3s)
[NodePalette] deepseek complete: 11 unique, 4 duplicates (2.5s)
[NodePalette] Batch 1 complete (2.8s) | New: 45 | Total: 45
```

#### **Expected Behavior:**
- ✅ **Circles appear progressively** (1-2 per second)
- ✅ **From all 4 LLMs concurrently** (mixed order: qwen, deepseek, hunyuan, kimi)
- ✅ **NOT in batches** (old: wait 8s, then 60 circles at once ❌)
- ✅ **Smooth appearance** (no lag or freeze)

#### **Server Logs (Terminal/Console):**
```
[NodePaletteV2] Batch 1 starting | Session: abc123de | Topic: '汽车'
[NodePaletteV2] Streaming from 4 LLMs with progressive rendering...
[LLMService] stream_progressive() - streaming from 4 models concurrently
[LLMService] qwen stream complete - 127 tokens in 2.31s (55.0 tok/s)
[LLMService] deepseek stream complete - 112 tokens in 2.45s (45.7 tok/s)
[NodePaletteV2] qwen batch 1 complete | Unique: 12 | Duplicates: 3 | Time: 2.31s
[NodePaletteV2] Batch 1 complete (2.78s) | New unique: 45 | Total: 45
```

### **Step 6: Test Infinite Scroll**
1. Scroll down to 2/3 of Node Palette container
2. **Should trigger:** Next batch (4 LLMs fire again)
3. More circles appear progressively
4. No duplicates

### **Step 7: Test Node Selection**
1. Click on some nodes to select them
2. Selected nodes should have blue border
3. Click **"Finish"** button
4. Node Palette closes
5. Selected nodes appear in Circle Map

---

## 🐛 Edge Case Testing

### **Test 1: Network Error**
1. Disconnect internet mid-stream
2. **Expected:** Error event in console, other LLMs continue
3. **Log:** `[NodePaletteV2] {llm} stream error: {error}`

### **Test 2: Timeout**
1. Use slow LLM (kimi usually takes longest)
2. **Expected:** Timeout after 20s, error logged
3. **Other LLMs:** Continue normally

### **Test 3: Duplicate Detection**
1. Generate first batch
2. Scroll for second batch
3. **Expected:** Some duplicates filtered
4. **Log:** `Duplicates: X` count increases

---

## 📊 Performance Validation

### **Timing Comparison:**

#### **Before (Sequential V1):**
```
Batch 1: qwen (2s) → deepseek (3s) → hunyuan (4s) → kimi (8s)
Total: 8 seconds wait → 60 nodes appear at once
UX: ⭐⭐ Slow & choppy
```

#### **After (Concurrent Streaming V2):**
```
Batch 1: All 4 fire simultaneously
qwen: 2s → nodes appear immediately
deepseek: 2.5s → nodes appear immediately  
hunyuan: 3s → nodes appear immediately
kimi: 8s → nodes appear immediately
Total: 8 seconds BUT nodes render progressively
UX: ⭐⭐⭐⭐ Smooth & responsive
```

**Key Metrics to Check:**
- ✅ **First node appears:** < 2s (was ~8s)
- ✅ **All nodes render:** ~8s (same, but progressive)
- ✅ **User sees progress:** Immediate (was: blank screen 8s)

---

## ✅ Success Criteria

### **Must Pass:**
- [ ] 4 LLMs fire simultaneously (check logs)
- [ ] Circles appear progressively (not in batch)
- [ ] Circles from different LLMs intermixed
- [ ] No errors in browser console
- [ ] No errors in server logs
- [ ] Scroll triggers next batch
- [ ] Duplicates are filtered
- [ ] Selected nodes add to Circle Map

### **Performance:**
- [ ] First circle appears < 2s
- [ ] Smooth rendering (no lag)
- [ ] Logs are clean (no token spam)

---

## 🔧 Troubleshooting

### **Problem: Circles appear in batch (not progressive)**
**Cause:** Server still using old V1 generator  
**Fix:**
```powershell
Get-ChildItem -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Filter "*.pyc" -Recurse | Remove-Item -Force
# Restart server
```

### **Problem: Only 1 LLM fires (not concurrent)**
**Cause:** Middleware not being used  
**Fix:** Check `node_palette_generator_v2.py` line 121:
```python
async for chunk in self.llm_service.stream_progressive(  # Should be this!
```

### **Problem: Logs show 500 lines/sec (token spam)**
**Cause:** Debug logging enabled  
**Fix:** Set `LOG_LEVEL=INFO` in environment

---

## 🚀 Next Steps After Testing

### **If All Tests Pass:**
1. ✅ Mark Phase 5 complete
2. ✅ Proceed to Phase 6: Edge case testing
3. ✅ Run performance benchmarks (Phase 7)
4. ✅ Final commit & merge (Phase 11)

### **If Issues Found:**
1. 🔍 Check error logs
2. 🐛 Debug specific issue
3. 🔄 Apply rollback plan if needed (Phase 8)

---

## 📝 Testing Checklist

**Quick Test (5 min):**
- [ ] Server running on port 9527
- [ ] Circle Map created
- [ ] Node Palette opens
- [ ] Circles appear progressively
- [ ] All 4 LLMs fire (check console)

**Full Test (15 min):**
- [ ] All quick test items
- [ ] Infinite scroll works
- [ ] Duplicates filtered
- [ ] Selected nodes added to map
- [ ] Edge cases tested
- [ ] Performance validated

---

## 📂 Test Environment

**Branch:** `feature/concurrent-token-streaming`  
**Server:** http://localhost:9527  
**Key Files Modified:**
- `services/llm_service.py` (added `stream_progressive()`)
- `agents/thinking_modes/node_palette_generator_v2.py` (uses middleware)

**Rollback Point:** Commit `ba7df7f` (backup before implementation)

---

**Ready to test!** Open http://localhost:9527 and follow the steps above. 🚀

