import { onUnmounted, ref } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import type { BranchMoveGhostPreview, DropTarget } from '@/composables/editor/useBranchMoveDrag'
import { PALETTE_MINDMAP_DRAG_MIME } from '@/composables/nodePalette/constants'
import {
  endMindMapPaletteDrag,
  getMindMapPaletteDragSession,
  type MindMapPaletteDragItem,
} from '@/composables/nodePalette/mindMapPaletteDragSession'
import { getAiBrainstorm } from '@/composables/aiBrainstorm/useAiBrainstorm'
import { useLanguage } from '@/composables/core/useLanguage'
import { mindMapBranchFontSize, resolveMindMapTopicBorderColor } from '@/config/mindMapGeometry'
import { getMindMapThemeForDiagram } from '@/config/mindMapThemes'
import { useDiagramStore } from '@/stores'
import { isDiagramPresentationReadOnly } from '@/stores/diagram/presentationReadOnlyGuard'
import { estimateNodeWidth, measureBranchNodeHeight } from '@/stores/specLoader/mindMap'
import type { MindGraphNode } from '@/types'

export interface UseDiagramCanvasMindMapPaletteDropOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
}

interface MindMapPaletteDragPayload {
  items: MindMapPaletteDragItem[]
}

export interface MindMapPaletteDragPreviewState {
  active: boolean
  cursorPos: { x: number; y: number } | null
  draggedGhost: BranchMoveGhostPreview | null
  dropTarget: DropTarget | null
}

const DEFAULT_NODE_WIDTH = 120
const DEFAULT_NODE_HEIGHT = 50
const GHOST_BRANCH_ID = 'branch-r-1-0'

function resolveDropTargetNodeId(clientX: number, clientY: number): string | null {
  const el = document.elementFromPoint(clientX, clientY)
  const nodeEl = el?.closest('.vue-flow__node') as HTMLElement | null
  return nodeEl?.dataset?.id ?? null
}

function buildPaletteGhostLabel(items: MindMapPaletteDragItem[]): string {
  const first = (items[0]?.text ?? '').trim()
  if (!first) return '…'
  if (items.length <= 1) return first
  return `${first} (+${items.length - 1})`
}

function buildPaletteDragGhost(
  items: MindMapPaletteDragItem[],
  diagramData: ReturnType<typeof useDiagramStore>['data']
): BranchMoveGhostPreview | null {
  const texts = items.map((i) => (i.text ?? '').trim()).filter(Boolean)
  if (texts.length === 0) return null

  const label = buildPaletteGhostLabel(items)
  const theme = getMindMapThemeForDiagram(diagramData)
  const topicNode = diagramData?.nodes?.find((n) => n.id === 'topic')
  const width = Math.max(estimateNodeWidth(label, GHOST_BRANCH_ID), DEFAULT_NODE_WIDTH)
  const height = Math.max(measureBranchNodeHeight(label, GHOST_BRANCH_ID), DEFAULT_NODE_HEIGHT)

  return {
    label,
    width,
    height,
    backgroundColor: theme.backgroundColor,
    textColor: theme.textColor,
    borderColor: resolveMindMapTopicBorderColor(topicNode) ?? theme.borderColor,
    fontSize: `${mindMapBranchFontSize(GHOST_BRANCH_ID)}px`,
    fontWeight: 'normal',
    borderRadius: '9999px',
    shapeClass: 'is-pill',
    variant: 'standard',
  }
}

function resolvePaletteDropTarget(
  clientX: number,
  clientY: number,
  vfNodes: MindGraphNode[]
): DropTarget | null {
  const targetId = resolveDropTargetNodeId(clientX, clientY)
  if (targetId === 'topic') return { type: 'topic', nodeId: 'topic' }
  if (targetId?.startsWith('branch-')) return { type: 'child', nodeId: targetId }

  const onCanvas = Boolean(
    document.elementFromPoint(clientX, clientY)?.closest('.diagram-canvas, .vue-flow')
  )
  if (onCanvas && vfNodes.some((n) => n.id === 'topic')) {
    return { type: 'topic', nodeId: 'topic' }
  }
  return null
}

function clearPreviewState(state: {
  active: ReturnType<typeof ref<boolean>>
  cursorPos: ReturnType<typeof ref<{ x: number; y: number } | null>>
  draggedGhost: ReturnType<typeof ref<BranchMoveGhostPreview | null>>
  dropTarget: ReturnType<typeof ref<DropTarget | null>>
}): void {
  state.active.value = false
  state.cursorPos.value = null
  state.draggedGhost.value = null
  state.dropTarget.value = null
}

export function useDiagramCanvasMindMapPaletteDrop(
  options: UseDiagramCanvasMindMapPaletteDropOptions
) {
  const { diagramStore } = options
  const { screenToFlowCoordinate, getNodes } = useVueFlow()
  const { t } = useLanguage()
  const { removeDroppedSuggestions } = getAiBrainstorm()

  const previewActive = ref(false)
  const previewCursorPos = ref<{ x: number; y: number } | null>(null)
  const previewDraggedGhost = ref<BranchMoveGhostPreview | null>(null)
  const previewDropTarget = ref<DropTarget | null>(null)

  const previewState = ref<MindMapPaletteDragPreviewState>({
    active: false,
    cursorPos: null,
    draggedGhost: null,
    dropTarget: null,
  })

  function syncPreviewStateRef(): void {
    previewState.value = {
      active: previewActive.value,
      cursorPos: previewCursorPos.value,
      draggedGhost: previewDraggedGhost.value,
      dropTarget: previewDropTarget.value,
    }
  }

  function resetPreview(): void {
    clearPreviewState({
      active: previewActive,
      cursorPos: previewCursorPos,
      draggedGhost: previewDraggedGhost,
      dropTarget: previewDropTarget,
    })
    syncPreviewStateRef()
  }

  function updatePreviewFromDragEvent(event: DragEvent): void {
    const types = event.dataTransfer?.types ?? []
    if (!types.includes(PALETTE_MINDMAP_DRAG_MIME)) return

    const session = getMindMapPaletteDragSession()
    if (!session || session.items.length === 0) {
      resetPreview()
      return
    }

    const flowPos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
    const vfNodes = getNodes.value as MindGraphNode[]
    previewActive.value = true
    previewCursorPos.value = { x: flowPos.x, y: flowPos.y }
    previewDraggedGhost.value = buildPaletteDragGhost(session.items, diagramStore.data)
    previewDropTarget.value = resolvePaletteDropTarget(
      event.clientX,
      event.clientY,
      vfNodes
    )
    syncPreviewStateRef()
  }

  function handleGlobalDragEnd(): void {
    endMindMapPaletteDrag()
    resetPreview()
  }

  document.addEventListener('dragend', handleGlobalDragEnd)
  onUnmounted(() => {
    document.removeEventListener('dragend', handleGlobalDragEnd)
  })

  function isMindMapType(): boolean {
    const dt = diagramStore.type
    return dt === 'mindmap' || dt === 'mind_map'
  }

  function resolveBranchSide(topicNode: MindGraphNode, flowX: number): 'left' | 'right' {
    const pos = topicNode.position ?? { x: 0, y: 0 }
    const w =
      (topicNode as MindGraphNode & { dimensions?: { width?: number } }).dimensions?.width ?? 120
    const centerX = pos.x + w / 2
    return flowX < centerX ? 'left' : 'right'
  }

  function handleMindMapPaletteDragOver(event: DragEvent): void {
    if (!isMindMapType()) return
    const types = event.dataTransfer?.types ?? []
    if (types.includes(PALETTE_MINDMAP_DRAG_MIME) && event.dataTransfer) {
      event.preventDefault()
      event.dataTransfer.dropEffect = 'copy'
      updatePreviewFromDragEvent(event)
    }
  }

  function handleMindMapPaletteDragLeave(event: DragEvent): void {
    if (!isMindMapType()) return
    const related = event.relatedTarget as Node | null
    if (related && (event.currentTarget as Node | null)?.contains(related)) return
    resetPreview()
  }

  function handleMindMapPaletteDrop(event: DragEvent): void {
    if (isDiagramPresentationReadOnly()) return
    if (!isMindMapType()) return
    const raw = event.dataTransfer?.getData(PALETTE_MINDMAP_DRAG_MIME)
    resetPreview()
    endMindMapPaletteDrag()
    if (!raw) return

    event.preventDefault()

    let payload: MindMapPaletteDragPayload
    try {
      payload = JSON.parse(raw) as MindMapPaletteDragPayload
    } catch {
      return
    }

    const items = (payload.items ?? []).filter((item) => (item.text ?? '').trim())
    if (items.length === 0) return

    const targetId = resolveDropTargetNodeId(event.clientX, event.clientY)
    const flowPos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
    const vfNodes = getNodes.value as MindGraphNode[]
    const topicNode = vfNodes.find((n) => n.id === 'topic')

    diagramStore.pushHistory(t('canvas.mindMapWaterfall.historyAddFromPalette'))

    for (const item of items) {
      const text = item.text.trim()
      if (!text) continue

      if (targetId === 'topic' && topicNode) {
        const side = resolveBranchSide(topicNode, flowPos.x)
        diagramStore.addMindMapBranch(side, text)
      } else if (targetId?.startsWith('branch-')) {
        diagramStore.addMindMapChild(targetId, text)
      } else if (topicNode) {
        const side = resolveBranchSide(topicNode, flowPos.x)
        diagramStore.addMindMapBranch(side, text)
      }
    }

    removeDroppedSuggestions(items.map((i) => i.id))
  }

  return {
    handleMindMapPaletteDragOver,
    handleMindMapPaletteDragLeave,
    handleMindMapPaletteDrop,
    paletteDragPreview: previewState,
  }
}
