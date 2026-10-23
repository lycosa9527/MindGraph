/**
 * Node explanation stays unavailable while a node editor is still open.
 * The explanation must use the confirmed label; starting it on the same
 * gesture that commits the draft aborts the in-flight run.
 */
import { type ComputedRef, computed, ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { diagramSessionRef, useDiagramSession } from '@/composables/diagram/useDiagramSession'

const openEditIds = ref<string[]>([])
/** Outline edits do not emit node_editor events (those also claim collab). */
const outlineEditNodeId = ref<string | null>(null)
let installed = false

function rememberOpenEdit(nodeId: string): void {
  if (openEditIds.value.includes(nodeId)) return
  openEditIds.value = [...openEditIds.value, nodeId]
}

function forgetOpenEdit(nodeId: string): void {
  if (!openEditIds.value.includes(nodeId)) return
  openEditIds.value = openEditIds.value.filter((id) => id !== nodeId)
}

export function setNodeExplainOutlineEditing(nodeId: string | null): void {
  outlineEditNodeId.value = nodeId
}

export function ensureNodeExplainEditGate(): void {
  if (installed) return
  installed = true
  eventBus.on('node_editor:opening', ({ nodeId }) => {
    if (nodeId) rememberOpenEdit(nodeId)
  })
  eventBus.on('node_editor:closed', ({ nodeId }) => {
    if (nodeId) forgetOpenEdit(nodeId)
  })
}

export function openNodeExplainEditIds(): readonly string[] {
  return openEditIds.value
}

export function isNodeExplainLocked(options?: {
  editingNodeId?: string | null
  pendingEditNodeId?: string | null
}): boolean {
  if (outlineEditNodeId.value) return true
  if (openEditIds.value.length > 0) return true
  if (options?.editingNodeId) return true
  if (options?.pendingEditNodeId) return true
  return false
}

export function useNodeExplainEditGate(): { locked: ComputedRef<boolean> } {
  ensureNodeExplainEditGate()
  const diagramStore = useDiagramSession()
  const editingNodeId = diagramSessionRef(diagramStore, 'mindMapEditingNodeId')
  const pendingEditNodeId = diagramSessionRef(diagramStore, 'mindMapPendingEditNodeId')
  const locked = computed(() =>
    isNodeExplainLocked({
      editingNodeId: editingNodeId.value,
      pendingEditNodeId: pendingEditNodeId.value,
    })
  )
  return { locked }
}
