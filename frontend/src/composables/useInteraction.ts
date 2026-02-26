/**
 * useInteraction - Composable for diagram interaction handling
 *
 * Manages user interactions with diagram nodes:
 * - Selection (single/multi-select) with EventBus integration
 * - Double-click detection for text editing
 * - Drag events
 * - Event subscriptions for interaction requests
 *
 * Migrated from archive/static/js/managers/editor/interaction-handler.js
 */
import { onUnmounted, ref } from 'vue'

import type { MindGraphNode } from '@/types'

import { eventBus } from './useEventBus'
import { useSelection } from './useSelection'

// ============================================================================
// Types
// ============================================================================

export interface InteractionOptions {
  /** Enable multi-select with Ctrl/Cmd click */
  multiSelect?: boolean
  /** Threshold in ms for double-click detection */
  doubleClickThreshold?: number
  /** Owner ID for EventBus listener tracking */
  ownerId?: string
  /** Callback when text editing should start */
  onEditText?: (nodeId: string, currentText: string) => void
  /** Callback when node is dragged */
  onDragEnd?: (nodeId: string, position: { x: number; y: number }) => void
}

export interface ClickTracker {
  lastClickTime: number
  lastClickNodeId: string | null
  singleClickTimeout: ReturnType<typeof setTimeout> | null
}

// ============================================================================
// Composable
// ============================================================================

export function useInteraction(options: InteractionOptions = {}) {
  const {
    multiSelect = true,
    doubleClickThreshold = 250,
    ownerId = `Interaction_${Date.now()}`,
    onEditText,
    onDragEnd,
  } = options

  // Use the selection composable with EventBus notification
  const selection = useSelection({
    multiSelect,
    onSelectionChange: (state) => {
      // Emit selection changed event via EventBus
      eventBus.emit('interaction:selection_changed', {
        selectedNodes: Array.from(state.nodes),
      })
      eventBus.emit('state:selection_changed', {
        selectedNodes: Array.from(state.nodes),
      })
    },
  })

  // Double-click tracking
  const clickTracker = ref<ClickTracker>({
    lastClickTime: 0,
    lastClickNodeId: null,
    singleClickTimeout: null,
  })

  // Editing state
  const editingNodeId = ref<string | null>(null)

  // =========================================================================
  // Click Handling (with double-click detection)
  // =========================================================================

  /**
   * Handle node click with double-click detection
   * First click: delayed selection
   * Second click within threshold: open editor
   */
  function handleNodeClick(
    nodeId: string,
    event: MouseEvent,
    nodeData?: { label?: string; text?: string }
  ): void {
    const now = Date.now()
    const tracker = clickTracker.value
    const timeSinceLastClick = now - tracker.lastClickTime
    const isDoubleClick =
      timeSinceLastClick < doubleClickThreshold && tracker.lastClickNodeId === nodeId

    if (isDoubleClick) {
      // DOUBLE-CLICK: Cancel pending single-click and open editor
      if (tracker.singleClickTimeout) {
        clearTimeout(tracker.singleClickTimeout)
        tracker.singleClickTimeout = null
      }

      tracker.lastClickTime = 0
      tracker.lastClickNodeId = null

      // Emit event that editor is opening
      eventBus.emit('node_editor:opening', { nodeId })

      // Get current text and trigger edit callback
      const currentText = nodeData?.label || nodeData?.text || 'Edit me'
      editingNodeId.value = nodeId

      if (onEditText) {
        onEditText(nodeId, currentText)
      }
    } else {
      // FIRST CLICK: Record time and delay selection
      tracker.lastClickTime = now
      tracker.lastClickNodeId = nodeId

      // Cancel any pending timeout
      if (tracker.singleClickTimeout) {
        clearTimeout(tracker.singleClickTimeout)
      }

      const isMultiSelect = event.ctrlKey || event.metaKey

      // Delay selection to allow double-click detection
      tracker.singleClickTimeout = setTimeout(() => {
        tracker.singleClickTimeout = null

        if (isMultiSelect) {
          selection.toggleNodeSelection(nodeId)
        } else {
          selection.clearSelection()
          selection.selectNode(nodeId)
        }
      }, doubleClickThreshold)
    }
  }

  /**
   * Handle immediate node selection (no double-click detection)
   */
  function selectNodeImmediate(nodeId: string, addToSelection = false): void {
    if (addToSelection) {
      selection.toggleNodeSelection(nodeId)
    } else {
      selection.clearSelection()
      selection.selectNode(nodeId)
    }
  }

  // =========================================================================
  // Drag Handling
  // =========================================================================

  /**
   * Handle node drag start
   */
  function handleDragStart(nodeId: string, position: { x: number; y: number }): void {
    eventBus.emit('interaction:drag_started', { nodeId, position })
  }

  /**
   * Handle node drag end
   */
  function handleDragEnd(nodeId: string, position: { x: number; y: number }): void {
    eventBus.emit('interaction:drag_ended', { nodeId, position })

    if (onDragEnd) {
      onDragEnd(nodeId, position)
    }

    // Emit operation completed for history
    eventBus.emit('diagram:operation_completed', {
      operation: 'move_node',
      details: { nodeId, position },
    })
  }

  // =========================================================================
  // Text Editing
  // =========================================================================

  /**
   * Start text editing for a node
   */
  function startEditing(nodeId: string, currentText: string): void {
    editingNodeId.value = nodeId
    eventBus.emit('node_editor:opening', { nodeId })

    if (onEditText) {
      onEditText(nodeId, currentText)
    }
  }

  /**
   * Stop text editing
   */
  function stopEditing(): void {
    editingNodeId.value = null
  }

  // =========================================================================
  // EventBus Subscriptions
  // =========================================================================

  // Listen for selection requests via EventBus
  const unsubSelectNode = eventBus.onWithOwner(
    'interaction:select_node_requested',
    (data) => {
      if (data.nodeId) {
        selectNodeImmediate(data.nodeId, false)
      }
    },
    ownerId
  )

  // Listen for clear selection requests
  const unsubClearSelection = eventBus.onWithOwner(
    'interaction:clear_selection_requested',
    () => {
      selection.clearSelection()
    },
    ownerId
  )

  // Listen for edit text requests
  const unsubEditText = eventBus.onWithOwner(
    'interaction:edit_text_requested',
    (data) => {
      if (data.nodeId) {
        startEditing(data.nodeId, 'Edit me')
      }
    },
    ownerId
  )

  // Listen for selection highlight requests (from voice agent)
  const unsubHighlight = eventBus.onWithOwner(
    'selection:highlight_requested',
    (data) => {
      if (data.nodeId) {
        selection.clearSelection()
        selection.selectNode(data.nodeId)
      }
    },
    ownerId
  )

  // Listen for selection select requests (from voice agent)
  const unsubSelect = eventBus.onWithOwner(
    'selection:select_requested',
    (data) => {
      if (data.nodeId) {
        selection.clearSelection()
        selection.selectNode(data.nodeId)
      }
    },
    ownerId
  )

  // =========================================================================
  // Cleanup
  // =========================================================================

  function destroy(): void {
    // Clear any pending timeout and reset click tracker state
    if (clickTracker.value.singleClickTimeout) {
      clearTimeout(clickTracker.value.singleClickTimeout)
      clickTracker.value.singleClickTimeout = null
    }
    clickTracker.value.lastClickTime = 0
    clickTracker.value.lastClickNodeId = null

    // Unsubscribe from EventBus
    unsubSelectNode()
    unsubClearSelection()
    unsubEditText()
    unsubHighlight()
    unsubSelect()

    // Also remove all listeners for this owner (belt and suspenders)
    eventBus.removeAllListenersForOwner(ownerId)
  }

  // Cleanup on unmount
  onUnmounted(() => {
    destroy()
  })

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // Selection (delegated from useSelection)
    selectedNodeIds: selection.selectedNodeIds,
    selectedEdgeIds: selection.selectedEdgeIds,
    selectedNodes: selection.selectedNodes,
    selectedEdges: selection.selectedEdges,
    hasSelection: selection.hasSelection,
    selectionCount: selection.selectionCount,

    // Selection actions
    selectNode: selection.selectNode,
    selectNodes: selection.selectNodes,
    selectAll: selection.selectAll,
    toggleNodeSelection: selection.toggleNodeSelection,
    deselectNode: selection.deselectNode,
    clearSelection: selection.clearSelection,
    isNodeSelected: selection.isNodeSelected,
    getSelectedNodeData: selection.getSelectedNodeData,

    // Vue Flow event handlers
    onNodesSelectionChange: selection.onNodesSelectionChange,
    onEdgesSelectionChange: selection.onEdgesSelectionChange,

    // Click handling
    handleNodeClick,
    selectNodeImmediate,

    // Drag handling
    handleDragStart,
    handleDragEnd,

    // Text editing
    editingNodeId,
    startEditing,
    stopEditing,

    // Cleanup
    destroy,
  }
}

// ============================================================================
// Helper: Create interaction handlers for Vue Flow
// ============================================================================

/**
 * Create Vue Flow event handlers integrated with useInteraction
 */
export function createVueFlowHandlers(interaction: ReturnType<typeof useInteraction>) {
  return {
    onNodeClick: (event: MouseEvent, node: MindGraphNode) => {
      interaction.handleNodeClick(node.id, event, node.data)
    },

    onNodeDoubleClick: (_event: MouseEvent, node: MindGraphNode) => {
      const currentText =
        node.data?.label || (typeof node.data?.text === 'string' ? node.data.text : 'Edit me')
      interaction.startEditing(node.id, currentText)
    },

    onNodeDragStart: (event: { node: MindGraphNode }) => {
      interaction.handleDragStart(event.node.id, event.node.position)
    },

    onNodeDragStop: (event: { node: MindGraphNode }) => {
      interaction.handleDragEnd(event.node.id, event.node.position)
    },

    onPaneClick: () => {
      interaction.clearSelection()
    },

    onSelectionChange: (params: { nodes: MindGraphNode[] }) => {
      const changes = params.nodes.map((node) => ({
        id: node.id,
        selected: (node as unknown as { selected?: boolean }).selected ?? false,
      }))
      interaction.onNodesSelectionChange(changes)
    },
  }
}
