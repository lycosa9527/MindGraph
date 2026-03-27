/**
 * useSelection - Composable for Vue Flow node and edge selection management
 * Provides multi-select, shift-click, and selection state management
 */
import { computed, ref } from 'vue'

import type { MindGraphEdge, MindGraphNode } from '@/types'

export interface SelectionState {
  nodes: Set<string>
  edges: Set<string>
}

export interface UseSelectionOptions {
  multiSelect?: boolean
  onSelectionChange?: (state: SelectionState) => void
}

export function useSelection(options: UseSelectionOptions = {}) {
  const { multiSelect = true, onSelectionChange } = options

  // Selection state
  const selectedNodeIds = ref<Set<string>>(new Set())
  const selectedEdgeIds = ref<Set<string>>(new Set())
  const lastSelectedNodeId = ref<string | null>(null)

  // Computed selections
  const selectedNodes = computed(() => Array.from(selectedNodeIds.value))
  const selectedEdges = computed(() => Array.from(selectedEdgeIds.value))
  const hasSelection = computed(
    () => selectedNodeIds.value.size > 0 || selectedEdgeIds.value.size > 0
  )
  const selectionCount = computed(() => selectedNodeIds.value.size + selectedEdgeIds.value.size)

  // Notify selection change
  function notifyChange() {
    onSelectionChange?.({
      nodes: new Set(selectedNodeIds.value),
      edges: new Set(selectedEdgeIds.value),
    })
  }

  // Select a node
  function selectNode(nodeId: string, addToSelection = false) {
    if (!multiSelect || !addToSelection) {
      selectedNodeIds.value.clear()
      selectedEdgeIds.value.clear()
    }

    selectedNodeIds.value.add(nodeId)
    lastSelectedNodeId.value = nodeId
    notifyChange()
  }

  // Select an edge
  function selectEdge(edgeId: string, addToSelection = false) {
    if (!multiSelect || !addToSelection) {
      selectedNodeIds.value.clear()
      selectedEdgeIds.value.clear()
    }

    selectedEdgeIds.value.add(edgeId)
    notifyChange()
  }

  // Toggle node selection
  function toggleNodeSelection(nodeId: string) {
    if (selectedNodeIds.value.has(nodeId)) {
      selectedNodeIds.value.delete(nodeId)
    } else {
      selectedNodeIds.value.add(nodeId)
      lastSelectedNodeId.value = nodeId
    }
    notifyChange()
  }

  // Toggle edge selection
  function toggleEdgeSelection(edgeId: string) {
    if (selectedEdgeIds.value.has(edgeId)) {
      selectedEdgeIds.value.delete(edgeId)
    } else {
      selectedEdgeIds.value.add(edgeId)
    }
    notifyChange()
  }

  // Select multiple nodes
  function selectNodes(nodeIds: string[], addToSelection = false) {
    if (!addToSelection) {
      selectedNodeIds.value.clear()
      selectedEdgeIds.value.clear()
    }

    nodeIds.forEach((id) => selectedNodeIds.value.add(id))
    if (nodeIds.length > 0) {
      lastSelectedNodeId.value = nodeIds[nodeIds.length - 1]
    }
    notifyChange()
  }

  // Select all nodes
  function selectAll(nodes: MindGraphNode[]) {
    nodes.forEach((node) => selectedNodeIds.value.add(node.id))
    notifyChange()
  }

  // Deselect a node
  function deselectNode(nodeId: string) {
    selectedNodeIds.value.delete(nodeId)
    if (lastSelectedNodeId.value === nodeId) {
      lastSelectedNodeId.value = null
    }
    notifyChange()
  }

  // Deselect an edge
  function deselectEdge(edgeId: string) {
    selectedEdgeIds.value.delete(edgeId)
    notifyChange()
  }

  // Clear all selections
  function clearSelection() {
    selectedNodeIds.value.clear()
    selectedEdgeIds.value.clear()
    lastSelectedNodeId.value = null
    notifyChange()
  }

  // Check if a node is selected
  function isNodeSelected(nodeId: string): boolean {
    return selectedNodeIds.value.has(nodeId)
  }

  // Check if an edge is selected
  function isEdgeSelected(edgeId: string): boolean {
    return selectedEdgeIds.value.has(edgeId)
  }

  // Get selected node data from a nodes array
  function getSelectedNodeData(nodes: MindGraphNode[]): MindGraphNode[] {
    return nodes.filter((node) => selectedNodeIds.value.has(node.id))
  }

  // Get selected edge data from an edges array
  function getSelectedEdgeData(edges: MindGraphEdge[]): MindGraphEdge[] {
    return edges.filter((edge) => selectedEdgeIds.value.has(edge.id))
  }

  // Handle Vue Flow selection change event
  function onNodesSelectionChange(changes: { id: string; selected: boolean }[]) {
    changes.forEach((change) => {
      if (change.selected) {
        selectedNodeIds.value.add(change.id)
        lastSelectedNodeId.value = change.id
      } else {
        selectedNodeIds.value.delete(change.id)
      }
    })
    notifyChange()
  }

  // Handle Vue Flow edge selection change event
  function onEdgesSelectionChange(changes: { id: string; selected: boolean }[]) {
    changes.forEach((change) => {
      if (change.selected) {
        selectedEdgeIds.value.add(change.id)
      } else {
        selectedEdgeIds.value.delete(change.id)
      }
    })
    notifyChange()
  }

  // Invert selection
  function invertSelection(allNodes: MindGraphNode[]) {
    const newSelection = new Set<string>()
    allNodes.forEach((node) => {
      if (!selectedNodeIds.value.has(node.id)) {
        newSelection.add(node.id)
      }
    })
    selectedNodeIds.value = newSelection
    notifyChange()
  }

  // Select nodes by type
  function selectByType(nodes: MindGraphNode[], nodeType: string) {
    nodes.forEach((node) => {
      if (node.data?.nodeType === nodeType) {
        selectedNodeIds.value.add(node.id)
      }
    })
    notifyChange()
  }

  return {
    // State
    selectedNodeIds,
    selectedEdgeIds,
    lastSelectedNodeId,

    // Computed
    selectedNodes,
    selectedEdges,
    hasSelection,
    selectionCount,

    // Actions
    selectNode,
    selectEdge,
    toggleNodeSelection,
    toggleEdgeSelection,
    selectNodes,
    selectAll,
    deselectNode,
    deselectEdge,
    clearSelection,
    invertSelection,
    selectByType,

    // Queries
    isNodeSelected,
    isEdgeSelected,
    getSelectedNodeData,
    getSelectedEdgeData,

    // Event handlers
    onNodesSelectionChange,
    onEdgesSelectionChange,
  }
}
