/**
 * useHistory - Composable for undo/redo history management
 *
 * Handles:
 * - History stack with diagram snapshots
 * - Undo/redo operations
 * - Automatic snapshot on diagram operations
 * - EventBus integration for state changes
 *
 * Migrated from archive/static/js/managers/editor/history-manager.js
 */
import { computed, onUnmounted, ref, shallowRef } from 'vue'

import type { DiagramSpec } from '@/types'

import { eventBus } from './useEventBus'

// ============================================================================
// Types
// ============================================================================

export interface HistoryEntry {
  id: string
  action: string
  metadata: Record<string, unknown>
  spec: DiagramSpec
  timestamp: number
}

export interface HistoryState {
  size: number
  index: number
  canUndo: boolean
  canRedo: boolean
}

export interface UseHistoryOptions {
  ownerId?: string
  maxSize?: number
  onUndo?: (entry: HistoryEntry) => void
  onRedo?: (entry: HistoryEntry) => void
}

// ============================================================================
// Composable
// ============================================================================

export function useHistory(options: UseHistoryOptions = {}) {
  const { ownerId = `History_${Date.now()}`, maxSize = 50, onUndo, onRedo } = options

  // =========================================================================
  // State
  // =========================================================================

  const history = shallowRef<HistoryEntry[]>([])
  const historyIndex = ref(-1)

  // =========================================================================
  // Computed
  // =========================================================================

  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < history.value.length - 1)
  const historySize = computed(() => history.value.length)
  const currentEntry = computed(() => {
    if (historyIndex.value >= 0 && historyIndex.value < history.value.length) {
      return history.value[historyIndex.value]
    }
    return null
  })

  // =========================================================================
  // Helpers
  // =========================================================================

  function generateEntryId(): string {
    return `history_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
  }

  function deepClone<T>(obj: T): T {
    return JSON.parse(JSON.stringify(obj))
  }

  function emitStateChange(): void {
    eventBus.emit('history:state_changed', {
      canUndo: canUndo.value,
      canRedo: canRedo.value,
      historySize: historySize.value,
      historyIndex: historyIndex.value,
    })
  }

  // =========================================================================
  // Core Operations
  // =========================================================================

  /**
   * Save current state to history
   */
  function saveToHistory(
    action: string,
    spec: DiagramSpec,
    metadata: Record<string, unknown> = {}
  ): void {
    if (!spec) {
      console.warn('[History] Cannot save - no spec provided')
      return
    }

    // Remove any history after current index (branch cut)
    const newHistory = history.value.slice(0, historyIndex.value + 1)

    // Add new entry
    const entry: HistoryEntry = {
      id: generateEntryId(),
      action,
      metadata: deepClone(metadata),
      spec: deepClone(spec),
      timestamp: Date.now(),
    }

    newHistory.push(entry)

    // Limit history size
    if (newHistory.length > maxSize) {
      newHistory.shift()
    }

    history.value = newHistory
    historyIndex.value = newHistory.length - 1

    // Emit events
    eventBus.emit('history:saved', {
      action,
      metadata,
      historyIndex: historyIndex.value,
      historySize: historySize.value,
      canUndo: canUndo.value,
      canRedo: canRedo.value,
    })

    emitStateChange()
  }

  /**
   * Undo last operation
   */
  function undo(): HistoryEntry | null {
    if (!canUndo.value) {
      eventBus.emit('history:undo_failed', { reason: 'No more history to undo' })
      return null
    }

    historyIndex.value--
    const entry = history.value[historyIndex.value]

    // Emit undo completed with restored spec
    eventBus.emit('history:undo_completed', {
      action: entry.action,
      metadata: entry.metadata,
      spec: deepClone(entry.spec),
      historyIndex: historyIndex.value,
      canUndo: canUndo.value,
      canRedo: canRedo.value,
    })

    emitStateChange()
    onUndo?.(entry)

    return entry
  }

  /**
   * Redo last undone operation
   */
  function redo(): HistoryEntry | null {
    if (!canRedo.value) {
      eventBus.emit('history:redo_failed', { reason: 'No more history to redo' })
      return null
    }

    historyIndex.value++
    const entry = history.value[historyIndex.value]

    // Emit redo completed with restored spec
    eventBus.emit('history:redo_completed', {
      action: entry.action,
      metadata: entry.metadata,
      spec: deepClone(entry.spec),
      historyIndex: historyIndex.value,
      canUndo: canUndo.value,
      canRedo: canRedo.value,
    })

    emitStateChange()
    onRedo?.(entry)

    return entry
  }

  /**
   * Clear all history
   */
  function clearHistory(): void {
    history.value = []
    historyIndex.value = -1

    eventBus.emit('history:cleared', {
      canUndo: false,
      canRedo: false,
    })

    emitStateChange()
  }

  /**
   * Get snapshot at specific index
   */
  function getSnapshot(index: number): DiagramSpec | null {
    if (index < 0 || index >= history.value.length) {
      return null
    }
    return deepClone(history.value[index].spec)
  }

  /**
   * Get current history state
   */
  function getHistoryState(): HistoryState {
    return {
      size: historySize.value,
      index: historyIndex.value,
      canUndo: canUndo.value,
      canRedo: canRedo.value,
    }
  }

  /**
   * Initialize history with initial state
   */
  function initializeWithSpec(spec: DiagramSpec): void {
    clearHistory()
    saveToHistory('initial', spec)
  }

  // =========================================================================
  // EventBus Subscriptions
  // =========================================================================

  // Listen for diagram operations to auto-save
  eventBus.onWithOwner(
    'diagram:operation_completed',
    (data) => {
      if (data.snapshot || data.spec) {
        saveToHistory(
          (data.operation as string) || 'unknown',
          (data.snapshot || data.spec) as DiagramSpec,
          (data.details as Record<string, unknown>) || {}
        )
      }
    },
    ownerId
  )

  // Listen for undo requests
  eventBus.onWithOwner('history:undo_requested', () => undo(), ownerId)

  // Listen for redo requests
  eventBus.onWithOwner('history:redo_requested', () => redo(), ownerId)

  // Listen for clear requests
  eventBus.onWithOwner('history:clear_requested', () => clearHistory(), ownerId)

  // Listen for session ending to clear history
  eventBus.onWithOwner(
    'lifecycle:session_ending',
    () => {
      clearHistory()
    },
    ownerId
  )

  // =========================================================================
  // Cleanup
  // =========================================================================

  function destroy(): void {
    eventBus.removeAllListenersForOwner(ownerId)
    clearHistory()
  }

  onUnmounted(() => {
    destroy()
  })

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // State
    history,
    historyIndex,

    // Computed
    canUndo,
    canRedo,
    historySize,
    currentEntry,

    // Actions
    saveToHistory,
    undo,
    redo,
    clearHistory,
    getSnapshot,
    getHistoryState,
    initializeWithSpec,

    // Cleanup
    destroy,
  }
}

// ============================================================================
// Keyboard Integration Helper
// ============================================================================

/**
 * Create keyboard shortcuts for undo/redo
 * Usage: call in component setup with onMounted
 */
export function useHistoryKeyboard(historyInstance: ReturnType<typeof useHistory>): () => void {
  const handleKeydown = (e: KeyboardEvent) => {
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
    const modifier = isMac ? e.metaKey : e.ctrlKey

    if (modifier && e.key === 'z') {
      if (e.shiftKey) {
        // Ctrl/Cmd + Shift + Z = Redo
        e.preventDefault()
        historyInstance.redo()
      } else {
        // Ctrl/Cmd + Z = Undo
        e.preventDefault()
        historyInstance.undo()
      }
    } else if (modifier && e.key === 'y') {
      // Ctrl/Cmd + Y = Redo (Windows style)
      e.preventDefault()
      historyInstance.redo()
    }
  }

  window.addEventListener('keydown', handleKeydown)

  // Return cleanup function
  return () => {
    window.removeEventListener('keydown', handleKeydown)
  }
}
