# Root Cause: Mindmap Auto-Complete – User-Added Branches Disappear After Model Switch

## Symptom
After auto-complete finishes, user adds more branch/child nodes. When switching to another AI model and back, the user-added branches disappear.

## Root Cause
**User edits are never merged into the LLM result cache.** When switching models, we always load from `llmResultsStore.results[model].spec`, which holds the original AI-generated spec. User-added branches are not persisted there.

### Flow
1. Auto-complete finishes → each model's result stored in `results[model].spec` (original AI output)
2. User adds branches → `diagramStore.data` updated; fingerprint changes; auto-save debounced
3. User switches to Model B:
   - `saveCurrentDiagramBeforeReplace()` saves current diagram (with user edits) to backend ✓
   - `loadFromSpec(result.spec)` loads Model B's **original** spec from cache (no user edits)
4. User switches back to Model A:
   - `saveCurrentDiagramBeforeReplace()` saves Model B to backend
   - `loadFromSpec(result.spec)` loads Model A's **original** spec from cache
   - User's branches (added while on Model A) are lost

### Why fingerprint is not the bug
The content fingerprint in `useDiagramAutoSave` correctly detects changes (nodes/connections). Auto-save and save-before-replace both persist to the backend. The issue is that **model switching loads from the in-memory LLM cache**, not from the backend. The cache is never updated with user edits.

## Fix
When user edits are persisted, update the **current model's** result in the LLM cache with the new spec. Then switching away and back will load the updated spec including user edits.

## Workflow Review – All Persistence Paths

| Path | Calls updateCurrentModelSpec? | Notes |
|------|-------------------------------|-------|
| **useDiagramAutoSave.performSave** | ✓ After save success | Fingerprint/watch + llm:generation_completed |
| **saveCurrentDiagramBeforeReplace** | ✓ Before save (so llm_results includes it) | Before model switch; now preserves llm_results |
| **manualSaveDiagram** (update + save) | ✓ On success | CanvasTopBar, WorkshopModal, CanvasPage import |
| **deleteAndSave** | ✓ On success | Slot-full flow |
| **useDiagramSpecForSave.getDiagramSpec** | ✓ Before getResultsForPersistence | Ensures persisted llm_results has user edits when saving to backend |

### Load-from-library
When loading a diagram with `llm_results`, we restore the cache. The saved spec must include the updated cache (with user edits). That happens because:
- `getDiagramSpec()` calls `updateCurrentModelSpec(base)` before `getResultsForPersistence()`
- So `llm_results` in the saved spec reflects user edits
