/**
 * Canvas node visual indicator state — drives workshop-editing, collab-remote-selected,
 * and tab-rec-active CSS classes via Vue Flow's reactive node.class / node.style system.
 *
 * Composables write to this store; useDiagramCanvasNodesEdges reads it and merges
 * class + style into the nodes computed, so Vue Flow re-renders nodes automatically.
 * No document.querySelector class writes anywhere.
 */
import { ref } from 'vue'

import { defineStore } from 'pinia'

export interface WorkshopEditIndicator {
  /** Sampled once from DOM when the WS edit-start message arrives. */
  antColor: string
  editorColor: string
  emoji: string
  label: string
}

export const useCanvasNodeIndicatorsStore = defineStore('canvasNodeIndicators', () => {
  /** nodeId → editor info; present while a remote peer is editing that node. */
  const workshopEditing = ref(new Map<string, WorkshopEditIndicator>())
  /** nodeIds currently selected by a remote peer. */
  const collabSelected = ref(new Set<string>())
  /** nodeId with the active AI tab-rec picker open; null when picker is dismissed. */
  const tabRecActive = ref<string | null>(null)
  /**
   * Edge IDs to animate with the tab-rec ant line.
   * Non-empty in concept map relationship-label mode: the ant line goes on the
   * primary incident edge instead of the node.  Empty in all other cases.
   */
  const tabRecEdgeIds = ref<string[]>([])

  function setWorkshopEditing(nodeId: string, indicator: WorkshopEditIndicator): void {
    const next = new Map(workshopEditing.value)
    next.set(nodeId, indicator)
    workshopEditing.value = next
  }

  function clearWorkshopEditing(nodeId: string): void {
    if (!workshopEditing.value.has(nodeId)) return
    const next = new Map(workshopEditing.value)
    next.delete(nodeId)
    workshopEditing.value = next
  }

  function setCollabSelected(nodeIds: string[]): void {
    collabSelected.value = new Set(nodeIds)
  }

  function setTabRecActive(nodeId: string | null): void {
    tabRecActive.value = nodeId
  }

  function setTabRecEdgeIds(edgeIds: string[]): void {
    tabRecEdgeIds.value = edgeIds
  }

  /** Wipe all indicator maps — canvas Reset and leave-canvas teardown. */
  function clearAll(): void {
    workshopEditing.value = new Map()
    collabSelected.value = new Set()
    tabRecActive.value = null
    tabRecEdgeIds.value = []
  }

  return {
    workshopEditing,
    collabSelected,
    tabRecActive,
    tabRecEdgeIds,
    setWorkshopEditing,
    clearWorkshopEditing,
    setCollabSelected,
    setTabRecActive,
    setTabRecEdgeIds,
    clearAll,
  }
})
