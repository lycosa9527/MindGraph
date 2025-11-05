# Manager Lifecycle Audit

## Summary

This document audits all managers to verify they are correctly categorized as global vs session-scoped, and that leak detection is properly configured.

**Last Updated**: 2025-11-05

---

## Managers with ownerId (22 total)

### Global Managers (1)
These managers persist across sessions and their listeners are expected:

1. **PanelManager** ✅
   - Created: Page load (panel-manager.js:545)
   - ownerId: `'PanelManager'`
   - Listeners: 4 (panel:open_requested, panel:close_requested, panel:toggle_requested, panel:close_all_requested)
   - Status: ✅ Correctly in `globalOwners` list

### Session-Scoped Managers (21)
These managers are created per session, registered with SessionLifecycleManager, and should have no listeners after cleanup:

1. **InteractiveEditor** ✅
   - ownerId: `'InteractiveEditor'`
   - Status: ✅ In sessionOwners list

2. **ToolbarManager** ✅
   - ownerId: `'ToolbarManager'`
   - Status: ✅ In sessionOwners list

3. **SessionManager** ✅
   - ownerId: `'SessionManager'`
   - Status: ✅ In sessionOwners list

4. **NodePropertyOperationsManager** ✅
   - ownerId: `'NodePropertyOperationsManager'`
   - Status: ✅ In sessionOwners list

5. **LLMValidationManager** ✅
   - ownerId: `'LLMValidationManager'`
   - Status: ✅ In sessionOwners list

6. **NodeCounterFeatureModeManager** ✅
   - ownerId: `'NodeCounterFeatureModeManager'`
   - Status: ✅ In sessionOwners list

7. **SmallOperationsManager** ✅
   - ownerId: `'SmallOperationsManager'`
   - Status: ✅ In sessionOwners list

8. **TextToolbarStateManager** ✅
   - ownerId: `'TextToolbarStateManager'`
   - Status: ✅ In sessionOwners list

9. **UIStateLLMManager** ✅
   - ownerId: `'UIStateLLMManager'`
   - Status: ✅ In sessionOwners list

10. **VoiceAgentManager** ✅
    - ownerId: `'VoiceAgentManager'`
    - Status: ✅ In sessionOwners list

11. **ThinkGuideManager** ✅
    - ownerId: `'ThinkGuideManager'`
    - Status: ✅ In sessionOwners list

12. **AutoCompleteManager** ✅
    - ownerId: `'AutoCompleteManager'`
    - Status: ✅ In sessionOwners list

13. **PropertyPanelManager** ✅
    - ownerId: `'PropertyPanelManager'`
    - Status: ✅ In sessionOwners list

14. **ExportManager** ✅
    - ownerId: `'ExportManager'`
    - Status: ✅ In sessionOwners list

15. **DiagramOperationsLoader** ✅
    - ownerId: `'DiagramOperationsLoader'`
    - Status: ✅ In sessionOwners list

16. **MindMateManager** ✅
    - ownerId: `'MindMateManager'`
    - Status: ✅ In sessionOwners list

17. **CanvasController** ✅
    - ownerId: `'CanvasController'`
    - Status: ✅ In sessionOwners list

18. **HistoryManager** ✅
    - ownerId: `'HistoryManager'`
    - Status: ✅ In sessionOwners list

19. **InteractionHandler** ✅
    - ownerId: `'InteractionHandler'`
    - Status: ✅ In sessionOwners list

20. **ViewManager** ✅
    - ownerId: `'ViewManager'`
    - Status: ✅ In sessionOwners list

21. **LLMAutoCompleteManager** ✅
    - ownerId: `'LLMAutoCompleteManager'`
    - Status: ✅ In sessionOwners list

---

## Managers WITHOUT ownerId

These managers don't use Event Bus listeners, so they don't need ownerId:

1. **NodePaletteManager** ✅
   - No Event Bus listeners (verified: no eventBus.on or onWithOwner calls)
   - Status: ✅ Correctly NOT in leak detection list

---

## Core Infrastructure (Global, No ownerId)

These are global infrastructure components that don't use ownerId:

1. **EventBus** - Global singleton, manages all listeners
2. **StateManager** - Global singleton, doesn't register listeners
3. **Logger** - Global singleton, utility only
4. **SessionLifecycleManager** - Global singleton, manages lifecycle

---

## Verification Results

### ✅ All Managers Correctly Categorized

- **Global Managers**: 1 (PanelManager) ✅
- **Session-Scoped Managers**: 21 ✅
- **Managers without Event Bus**: 1 (NodePaletteManager) ✅

### ✅ Leak Detection Configuration

- **sessionOwners**: Contains all 21 session-scoped managers ✅
- **globalOwners**: Contains PanelManager only ✅
- **No missing managers**: All managers with ownerId are accounted for ✅

### ✅ No Issues Found

All managers are correctly categorized and leak detection is properly configured.

---

## Notes

- PanelManager was previously incorrectly flagged as a leak because it's global
- Fixed by moving PanelManager to `globalOwners` list (session-lifecycle.js:159)
- Global managers are now logged at DEBUG level only (not as warnings)


