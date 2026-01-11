/**
 * useDiagramPersistence - VueFlow State Persistence with VueUse
 *
 * Provides automatic persistence of VueFlow diagram state to localStorage
 * using VueUse's reactive storage utilities.
 *
 * Features:
 * - Auto-sync nodes/edges to localStorage
 * - Throttled saves for performance (avoids frequent writes)
 * - Restore functionality for loading persisted state
 * - Clear functionality for removing persisted data
 *
 * Usage:
 *   const { restore, clear, isPersisted } = useDiagramPersistence('my-diagram-id')
 *   onMounted(() => restore())
 */
import { type ComputedRef, computed, onUnmounted, watch } from 'vue'

import { type Edge, type Node, useVueFlow } from '@vue-flow/core'
import { useStorage, useThrottleFn } from '@vueuse/core'

// ============================================================================
// Types
// ============================================================================

export interface UseDiagramPersistenceOptions {
  /** Throttle delay for saves (ms) - default 1000ms */
  throttleDelay?: number
  /** Storage key prefix - default 'mindgraph' */
  keyPrefix?: string
  /** Auto-save on changes - default true */
  autoSave?: boolean
  /** Storage type - default localStorage */
  storage?: Storage
}

export interface DiagramPersistenceState {
  /** Restore persisted state to VueFlow */
  restore: () => boolean
  /** Save current state immediately (bypasses throttle) */
  saveNow: () => void
  /** Clear persisted data */
  clear: () => void
  /** Check if persisted data exists */
  isPersisted: ComputedRef<boolean>
  /** Enable/disable auto-save */
  setAutoSave: (enabled: boolean) => void
}

// ============================================================================
// Composable
// ============================================================================

export function useDiagramPersistence(
  diagramId: string,
  options: UseDiagramPersistenceOptions = {}
): DiagramPersistenceState {
  const {
    throttleDelay = 1000,
    keyPrefix = 'mindgraph',
    autoSave = true,
    storage = localStorage,
  } = options

  // Storage keys
  const nodesKey = `${keyPrefix}-${diagramId}-nodes`
  const edgesKey = `${keyPrefix}-${diagramId}-edges`

  // =========================================================================
  // VueFlow State
  // =========================================================================

  const { nodes, edges, setNodes, setEdges } = useVueFlow()

  // =========================================================================
  // VueUse: Reactive Storage
  // =========================================================================

  // Create reactive storage refs with empty arrays as defaults
  const persistedNodes = useStorage<Node[]>(nodesKey, [], storage, {
    mergeDefaults: false,
  })

  const persistedEdges = useStorage<Edge[]>(edgesKey, [], storage, {
    mergeDefaults: false,
  })

  // =========================================================================
  // Save Functions
  // =========================================================================

  /**
   * Save current VueFlow state to storage
   */
  function saveNow(): void {
    // Deep clone to avoid reactivity issues
    persistedNodes.value = JSON.parse(JSON.stringify(nodes.value))
    persistedEdges.value = JSON.parse(JSON.stringify(edges.value))
  }

  /**
   * Throttled save for performance (avoids frequent writes)
   */
  const throttledSave = useThrottleFn(saveNow, throttleDelay)

  // =========================================================================
  // Restore Function
  // =========================================================================

  /**
   * Restore persisted state to VueFlow
   * @returns true if state was restored, false if no persisted data
   */
  function restore(): boolean {
    const hasNodes = persistedNodes.value && persistedNodes.value.length > 0
    const hasEdges = persistedEdges.value && persistedEdges.value.length > 0

    if (!hasNodes && !hasEdges) {
      return false
    }

    if (hasNodes) {
      setNodes(persistedNodes.value)
    }

    if (hasEdges) {
      setEdges(persistedEdges.value)
    }

    return true
  }

  // =========================================================================
  // Clear Function
  // =========================================================================

  /**
   * Clear persisted data from storage
   */
  function clear(): void {
    persistedNodes.value = []
    persistedEdges.value = []
    storage.removeItem(nodesKey)
    storage.removeItem(edgesKey)
  }

  // =========================================================================
  // Auto-Save Watcher
  // =========================================================================

  let autoSaveEnabled = autoSave
  let stopWatcher: (() => void) | null = null

  function startAutoSave(): void {
    if (stopWatcher) return

    stopWatcher = watch(
      [nodes, edges],
      () => {
        if (autoSaveEnabled && nodes.value.length > 0) {
          throttledSave()
        }
      },
      { deep: true }
    )
  }

  function stopAutoSave(): void {
    if (stopWatcher) {
      stopWatcher()
      stopWatcher = null
    }
  }

  function setAutoSave(enabled: boolean): void {
    autoSaveEnabled = enabled
    if (enabled) {
      startAutoSave()
    } else {
      stopAutoSave()
    }
  }

  // Start auto-save if enabled
  if (autoSave) {
    startAutoSave()
  }

  // =========================================================================
  // Computed
  // =========================================================================

  const isPersisted = computed(() => {
    return (
      (persistedNodes.value && persistedNodes.value.length > 0) ||
      (persistedEdges.value && persistedEdges.value.length > 0)
    )
  })

  // =========================================================================
  // Cleanup
  // =========================================================================

  onUnmounted(() => {
    stopAutoSave()
  })

  // =========================================================================
  // Return
  // =========================================================================

  return {
    restore,
    saveNow,
    clear,
    isPersisted,
    setAutoSave,
  }
}
