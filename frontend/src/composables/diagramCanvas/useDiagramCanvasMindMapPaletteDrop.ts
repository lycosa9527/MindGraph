import { useVueFlow } from '@vue-flow/core'

import { PALETTE_MINDMAP_DRAG_MIME } from '@/composables/nodePalette/constants'
import { getNodePalette } from '@/composables/nodePalette/useNodePalette'
import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramStore } from '@/stores'
import type { MindGraphNode } from '@/types'

export interface UseDiagramCanvasMindMapPaletteDropOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
}

interface MindMapPaletteDragPayload {
  items: Array<{ id: string; text: string }>
}

function resolveDropTargetNodeId(clientX: number, clientY: number): string | null {
  const el = document.elementFromPoint(clientX, clientY)
  const nodeEl = el?.closest('.vue-flow__node') as HTMLElement | null
  return nodeEl?.dataset?.id ?? null
}

export function useDiagramCanvasMindMapPaletteDrop(
  options: UseDiagramCanvasMindMapPaletteDropOptions
) {
  const { diagramStore } = options
  const { screenToFlowCoordinate, getNodes } = useVueFlow()
  const { t } = useLanguage()
  const { removeDroppedSuggestions } = getNodePalette()

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
    }
  }

  function handleMindMapPaletteDrop(event: DragEvent): void {
    if (!isMindMapType()) return
    const raw = event.dataTransfer?.getData(PALETTE_MINDMAP_DRAG_MIME)
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
    handleMindMapPaletteDrop,
  }
}
