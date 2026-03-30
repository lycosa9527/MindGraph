import type { Ref } from 'vue'
import { nextTick } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { ANIMATION } from '@/config/uiConfig'
import { useDiagramStore } from '@/stores'
import type { Connection, DiagramNode, DiagramType, MindGraphNode } from '@/types'
import { normalizeAllConceptMapTopicRootLabels } from '@/utils/conceptMapTopicRootEdge'
import { waitForNextPaint } from '@/utils/diagramHtmlToImage'

type FitApi = {
  fitToFullCanvas: (animate?: boolean) => void
  fitWithPanel: (animate?: boolean) => void
  fitDiagram: (animate?: boolean) => void
  fitForExport: () => void
}

type DiagramStore = ReturnType<typeof useDiagramStore>

export interface DiagramCanvasEventBusContext {
  diagramStore: DiagramStore
  getNodes: () => MindGraphNode[]
  getViewport: () => { x: number; y: number; zoom: number }
  setViewport: (
    viewport: { x: number; y: number; zoom: number },
    opts?: { duration?: number }
  ) => void
  zoomIn: () => void
  zoomOut: () => void
  fitApi: FitApi
  emit: (e: 'nodeDoubleClick', node: MindGraphNode) => void
  exportByFormat: (format: string) => Promise<void>
  showExportToCommunityModal: Ref<boolean>
  regenerateForNodeIfNeeded: (nodeId: string) => void
}

const DOUBLE_BUBBLE_REBUILD_DEBOUNCE_MS = 16

export function useDiagramCanvasEventBus(): {
  mountSubscriptions: (ctx: DiagramCanvasEventBusContext) => () => void
  clearDoubleBubbleTimer: () => void
} {
  let doubleBubbleRebuildTimer: ReturnType<typeof setTimeout> | null = null

  function scheduleDoubleBubbleRebuild(diagramStore: DiagramStore): void {
    if (doubleBubbleRebuildTimer) clearTimeout(doubleBubbleRebuildTimer)
    doubleBubbleRebuildTimer = setTimeout(() => {
      doubleBubbleRebuildTimer = null
      const spec = diagramStore.getDoubleBubbleSpecFromData()
      if (spec) {
        diagramStore.loadFromSpec(spec, 'double_bubble_map', { emitLoaded: false })
      }
    }, DOUBLE_BUBBLE_REBUILD_DEBOUNCE_MS)
  }

  function clearDoubleBubbleTimer(): void {
    if (doubleBubbleRebuildTimer) {
      clearTimeout(doubleBubbleRebuildTimer)
      doubleBubbleRebuildTimer = null
    }
  }

  function mountSubscriptions(ctx: DiagramCanvasEventBusContext): () => void {
    const unsubscribers: (() => void)[] = []
    const {
      diagramStore,
      getNodes,
      getViewport,
      setViewport,
      zoomIn,
      zoomOut,
      fitApi,
      emit,
      exportByFormat,
      showExportToCommunityModal,
      regenerateForNodeIfNeeded,
    } = ctx

    unsubscribers.push(
      eventBus.on('node:edit_requested', ({ nodeId }) => {
        const node = getNodes().find((n) => n.id === nodeId)
        if (node) {
          emit('nodeDoubleClick', node as unknown as MindGraphNode)
        }
      })
    )

    unsubscribers.push(
      eventBus.on('view:fit_to_window_requested', (data) => {
        const animate = data?.animate !== false
        fitApi.fitToFullCanvas(animate)
      })
    )

    unsubscribers.push(
      eventBus.on('view:fit_to_canvas_requested', (data) => {
        const animate = data?.animate !== false
        fitApi.fitWithPanel(animate)
      })
    )

    unsubscribers.push(
      eventBus.on('diagram:branch_moved', () => {
        nextTick(() => {
          setTimeout(() => {
            eventBus.emit('view:fit_to_canvas_requested', { animate: true })
          }, ANIMATION.FIT_DELAY)
        })
      })
    )

    unsubscribers.push(
      eventBus.on('view:fit_diagram_requested', () => {
        fitApi.fitDiagram(true)
      })
    )

    // Reserved for callers that only want the export framing (no emit sites in repo today).
    unsubscribers.push(
      eventBus.on('view:fit_for_export_requested', () => {
        fitApi.fitForExport()
      })
    )

    unsubscribers.push(
      eventBus.on('toolbar:export_requested', async ({ format }) => {
        if (format === 'json') {
          await exportByFormat(format)
          return
        }

        if (format === 'community') {
          showExportToCommunityModal.value = true
          return
        }

        const savedViewport = getViewport()
        fitApi.fitForExport()
        await nextTick()
        await waitForNextPaint()
        await exportByFormat(format)
        setViewport(savedViewport, { duration: ANIMATION.DURATION_FAST })
      })
    )

    unsubscribers.push(
      eventBus.on('view:zoom_in_requested', () => {
        zoomIn()
      })
    )

    unsubscribers.push(
      eventBus.on('view:zoom_out_requested', () => {
        zoomOut()
      })
    )

    unsubscribers.push(
      eventBus.on('view:zoom_set_requested', ({ zoom }) => {
        const vp = getViewport()
        setViewport({ x: vp.x, y: vp.y, zoom }, { duration: ANIMATION.DURATION_FAST })
      })
    )

    unsubscribers.push(
      eventBus.on('node:text_updated', ({ nodeId, text }) => {
        const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
        const currentText = (node?.text ?? (node?.data as { label?: string })?.label ?? '').trim()
        const alreadyUpdated = currentText === text.trim()
        if (!alreadyUpdated) {
          diagramStore.pushHistory('Edit node text')
          diagramStore.updateNode(nodeId, { text })
          if (diagramStore.type === 'flow_map') {
            const spec = diagramStore.buildFlowMapSpecFromNodes()
            if (spec) {
              diagramStore.loadFromSpec(spec as Record<string, unknown>, 'flow_map' as DiagramType)
            }
          }
        }
        if (
          diagramStore.type === 'concept_map' &&
          diagramStore.data?.connections &&
          diagramStore.data.nodes
        ) {
          normalizeAllConceptMapTopicRootLabels(
            diagramStore.data.connections as Connection[],
            diagramStore.data.nodes as DiagramNode[]
          )
        }
        if (diagramStore.type === 'concept_map' && !alreadyUpdated) {
          regenerateForNodeIfNeeded(nodeId)
        }
        if (diagramStore.type === 'double_bubble_map') {
          scheduleDoubleBubbleRebuild(diagramStore)
        }
      })
    )

    unsubscribers.push(
      eventBus.on('multi_flow_map:topic_width_changed', ({ nodeId, width }) => {
        if (diagramStore.type !== 'multi_flow_map' || nodeId !== 'event' || width === null) {
          return
        }
        diagramStore.setTopicNodeWidth(width)
      })
    )

    unsubscribers.push(
      eventBus.on('multi_flow_map:node_width_changed', ({ nodeId, width }) => {
        if (diagramStore.type !== 'multi_flow_map' || !nodeId || width === null) {
          return
        }
        diagramStore.setNodeWidth(nodeId, width)
      })
    )

    return () => {
      unsubscribers.forEach((unsub) => unsub())
      unsubscribers.length = 0
    }
  }

  return {
    mountSubscriptions,
    clearDoubleBubbleTimer,
  }
}
