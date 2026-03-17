---
name: Inline Recommendations Fixes
overview: "Implement the remaining fixes from the inline recommendations code review: backend session TTL, router chunk logic, picker loading state, coordinator invalidation, shared constants, and cleanup error logging. Items 2.1 and 2.2 are already done."
todos: []
isProject: false
---

# Inline Recommendations Review Fixes

## Status: Already Fixed (Previous Session)

- **2.1 Critical** – Concurrent stream bug: `fetchNextBatch` guard added in [useInlineRecommendations.ts](frontend/src/composables/useInlineRecommendations.ts)
- **2.2 Medium** – `node_editor:tab_pressed` added to [useEventBus.ts](frontend/src/composables/useEventBus.ts) `EventTypes`

---

## Remaining Fixes

### 1. Medium: Backend Session TTL (2.3)

**Problem:** Sessions accumulate indefinitely if the client never calls cleanup.

**Approach:** Add a periodic prune task similar to [workshop_cleanup.py](services/workshop/workshop_cleanup.py).

**Changes:**

1. **Generator** – Add `prune_stale_sessions(max_age_seconds: int = 1800)` to [generator.py](agents/inline_recommendations/generator.py):
  - Iterate `session_start_times`; remove sessions older than TTL from all four dicts (`seen_texts`, `generated`, `batch_counts`, `session_start_times`)
  - Use `time.time()` for comparison
2. **Scheduler** – Create `agents/inline_recommendations/cleanup.py`:
  - `async def start_inline_rec_cleanup_scheduler(interval_minutes: int = 30)` – loop, sleep, call `get_inline_recommendations_generator().prune_stale_sessions(1800)`, handle `CancelledError` and exceptions
3. **Lifespan** – In [lifespan.py](services/infrastructure/lifecycle/lifespan.py):
  - Import and start `start_inline_rec_cleanup_scheduler(interval_minutes=30)` after workshop cleanup (same pattern)

---

### 2. Low: Router `chunk_count == 0` Logic (2.4)

**Location:** [routers/inline_recommendations.py](routers/inline_recommendations.py) – `_stream_recommendations`

**Change:** Track whether an error was already yielded. In `finally`, yield "No response" only when `chunk_count == 0` and no error was yielded.

```python
error_yielded = False
# In each except block: error_yielded = True before yield
# In finally: if chunk_count == 0 and not error_yielded: yield ...
```

---

### 3. Low: Picker Loading State (2.5)

**Location:** [InlineRecommendationsPicker.vue](frontend/src/components/canvas/InlineRecommendationsPicker.vue), [inlineRecommendations.ts](frontend/src/stores/inlineRecommendations.ts), [useInlineRecommendations.ts](frontend/src/composables/useInlineRecommendations.ts)

**Changes:**

1. **Store** – Add `fetchingNextBatchNodeIds: ref<Set<string>>(new Set())`, plus `setFetchingNextBatch(nodeId, bool)` and expose it. Clear in `invalidateAll` / `invalidateForNode`.
2. **Composable** – In `fetchNextBatch`: call `store.setFetchingNextBatch(nodeId, true)` at start, `store.setFetchingNextBatch(nodeId, false)` in `finally`.
3. **Picker** – Use `storeToRefs(store).fetchingNextBatchNodeIds`, compute `isFetchingNext = activeId && store.fetchingNextBatchNodeIds.has(activeId)`. Disable the next button (`:disabled="isFetchingNext"`) and optionally show a loading indicator.

---

### 4. Low: `onOtherNodeUpdated` Invalidation (2.6)

**Location:** [useInlineRecommendationsCoordinator.ts](frontend/src/composables/useInlineRecommendationsCoordinator.ts)

**Change:** Invalidate when the user edits another node and we have an active picker **or** we are generating for the active node. Current condition only checks options.

```typescript
function onOtherNodeUpdated(nodeId: string): void {
  const activeId = store.activeNodeId
  if (!activeId) return
  const hasOptions = (store.options[activeId]?.length ?? 0) > 0
  const isGenerating = store.generatingNodeIds.has(activeId)
  if (hasOptions || isGenerating) {
    store.invalidateForNode(activeId)
  }
}
```

---

### 5. Low: Shared Constants (5.2)

**Location:** [composables/nodePalette/constants.ts](frontend/src/composables/nodePalette/constants.ts)

**Change:** Add:

```typescript
export const INLINE_RECOMMENDATIONS_SUPPORTED_TYPES = [
  'mindmap', 'flow_map', 'tree_map', 'brace_map', 'circle_map',
  'bubble_map', 'double_bubble_map', 'multi_flow_map', 'bridge_map',
] as const
```

Update imports in:

- [useInlineRecommendations.ts](frontend/src/composables/useInlineRecommendations.ts) – replace local `SUPPORTED_TYPES`
- [useInlineRecommendationsCoordinator.ts](frontend/src/composables/useInlineRecommendationsCoordinator.ts) – replace local `SUPPORTED_TYPES`
- [CanvasPage.vue](frontend/src/pages/CanvasPage.vue) – replace `INLINE_REC_TYPES` with `INLINE_RECOMMENDATIONS_SUPPORTED_TYPES`

---

### 6. Low: Cleanup Error Logging (5.2)

**Location:** [inlineRecommendations.ts](frontend/src/stores/inlineRecommendations.ts) – `cleanupBackendSessions`

**Change:** Replace `.catch(() => {})` with `.catch((err) => { console.warn('[InlineRec] Cleanup failed:', err) })` (or use a shared logger if available).

---

## File Summary


| File                                                              | Action                                                      |
| ----------------------------------------------------------------- | ----------------------------------------------------------- |
| `agents/inline_recommendations/generator.py`                      | Add `prune_stale_sessions`                                  |
| `agents/inline_recommendations/cleanup.py`                        | New file – scheduler                                        |
| `agents/inline_recommendations/__init__.py`                       | Export cleanup scheduler                                    |
| `services/infrastructure/lifecycle/lifespan.py`                   | Start inline rec cleanup task                               |
| `routers/inline_recommendations.py`                               | Fix `chunk_count` / error-yield logic                       |
| `frontend/src/stores/inlineRecommendations.ts`                    | Add `fetchingNextBatchNodeIds`, fix cleanup logging         |
| `frontend/src/composables/useInlineRecommendations.ts`            | Use shared constant, set fetching state in `fetchNextBatch` |
| `frontend/src/composables/useInlineRecommendationsCoordinator.ts` | Use shared constant, update `onOtherNodeUpdated`            |
| `frontend/src/composables/nodePalette/constants.ts`               | Add `INLINE_RECOMMENDATIONS_SUPPORTED_TYPES`                |
| `frontend/src/pages/CanvasPage.vue`                               | Use shared constant                                         |
| `frontend/src/components/canvas/InlineRecommendationsPicker.vue`  | Add loading state for next button                           |


---

## Execution Order

1. Backend: generator `prune_stale_sessions` → cleanup scheduler → lifespan
2. Backend: router chunk logic
3. Frontend: shared constants (enables other frontend changes)
4. Frontend: store `fetchingNextBatchNodeIds` + cleanup logging
5. Frontend: composable updates (fetchNextBatch, coordinator)
6. Frontend: picker loading state
7. Frontend: CanvasPage constant

