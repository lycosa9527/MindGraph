import type { Ref } from 'vue'
import { nextTick, toValue } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import type { CanvasExportOptions } from '@/config/canvasExportOptions'
import { ANIMATION } from '@/config/uiConfig'
import { useCanvasExportStore } from '@/stores'
import { isDiagramPresentationReadOnly } from '@/stores/diagram/presentationReadOnlyGuard'
import { useUIStore } from '@/stores/ui'
import type { Connection, DiagramNode, DiagramType, MindGraphNode } from '@/types'
import { runWithExportVisualMode } from '@/utils/canvasExportVisualMode'
import { isManualViewportMode } from '@/utils/conceptMapDesktopViewport'
import { normalizeAllConceptMapTopicRootLabels } from '@/utils/conceptMapTopicRootEdge'
import { waitForNextPaint } from '@/utils/diagramHtmlToImage'
import { mergeCanvasExportOptions } from '@/utils/mergeCanvasExportOptions'

type FitApi = {
  fitToFullCanvas: (animate?: boolean) => void
  fitWithPanel: (animate?: boolean) => void
  fitDiagram: (animate?: boolean) => void
  fitForExport: () => void
  fitToNodes: (
    nodeIds: string[],
    options?: { animate?: boolean; duration?: number; padding?: number }
  ) => Promise<void>
  ensureNodeVisibleInSafeFraction: (
    nodeId: string,
    options?: { safeFraction?: number; animate?: boolean }
  ) => void
}

type DiagramStore = ReturnType<typeof useDiagramSession>

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
  exportByFormat: (format: string, options?: CanvasExportOptions) => Promise<void>
  capturePngBlob: (options?: CanvasExportOptions, asShown?: boolean) => Promise<Blob>
  copyPngToClipboard: (blobSource: Promise<Blob>) => Promise<void>
  showExportToCommunityModal: Ref<boolean>
  getExportContainer: () => HTMLElement | null
  prepareForCommunityExport: () => Promise<void>
  restoreViewportAfterCommunityExport: () => void
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
        diagramStore.loadFromSpec(spec, 'double_bubble_map', {
          emitLoaded: false,
          mergePreviousNodeStyles: true,
        })
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
    const uiStore = useUIStore()
    const canvasExportStore = useCanvasExportStore()
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
      capturePngBlob,
      copyPngToClipboard,
      showExportToCommunityModal,
      getExportContainer,
      prepareForCommunityExport,
      regenerateForNodeIfNeeded,
    } = ctx

    const viewBus = diagramStore.viewBus
    const sessionReadonly = () => toValue(diagramStore.isReadonly)

    unsubscribers.push(
      viewBus.on('node:edit_requested', ({ nodeId }) => {
        if (sessionReadonly()) return
        const node = getNodes().find((n) => n.id === nodeId)
        if (node) {
          emit('nodeDoubleClick', node as unknown as MindGraphNode)
        }
      })
    )

    unsubscribers.push(
      viewBus.on('diagram:double_bubble_relayout_requested', () => {
        if (sessionReadonly()) return
        if (diagramStore.type === 'double_bubble_map') {
          scheduleDoubleBubbleRebuild(diagramStore)
        }
      })
    )

    function allowViewportFitEvent(
      data: { userInitiated?: boolean; forExport?: boolean } | undefined
    ): boolean {
      // Readonly preview sessions must accept auto fit-on-init / reset.
      if (sessionReadonly()) return true
      if (!isManualViewportMode(diagramStore, uiStore)) return true
      return Boolean(data?.userInitiated || data?.forExport)
    }

    unsubscribers.push(
      viewBus.on('view:fit_to_window_requested', (data) => {
        if (!allowViewportFitEvent(data)) return
        const animate = data?.animate !== false
        fitApi.fitToFullCanvas(animate)
      })
    )

    unsubscribers.push(
      viewBus.on('view:fit_to_canvas_requested', (data) => {
        if (!allowViewportFitEvent(data)) return
        const animate = data?.animate !== false
        fitApi.fitWithPanel(animate)
      })
    )

    unsubscribers.push(
      viewBus.on('view:fit_to_nodes_requested', (data) => {
        if (!allowViewportFitEvent(data)) return
        void fitApi.fitToNodes(data.nodeIds, {
          animate: data.animate !== false,
          duration: data.duration,
          padding: data.padding,
        })
      })
    )

    // Pan-only keep-in-view after child add — always allowed (does not zoom-fit).
    unsubscribers.push(
      viewBus.on('view:ensure_node_visible_requested', (data) => {
        if (!data?.nodeId) return
        fitApi.ensureNodeVisibleInSafeFraction(data.nodeId, {
          safeFraction: data.safeFraction,
          animate: data.animate !== false,
        })
      })
    )

    unsubscribers.push(
      viewBus.on('diagram:branch_moved', () => {
        if (sessionReadonly()) return
        if (isManualViewportMode(diagramStore, uiStore)) return
        setTimeout(() => {
          viewBus.emit('view:fit_to_canvas_requested', { animate: true })
        }, ANIMATION.FIT_DELAY)
      })
    )

    unsubscribers.push(
      viewBus.on('view:fit_diagram_requested', () => {
        if (isManualViewportMode(diagramStore, uiStore) && !sessionReadonly()) return
        fitApi.fitDiagram(true)
      })
    )

    // Reserved for callers that only want the export framing (no emit sites in repo today).
    unsubscribers.push(
      viewBus.on('view:fit_for_export_requested', () => {
        fitApi.fitForExport()
      })
    )

    if (sessionReadonly()) {
      unsubscribers.push(
        viewBus.on('view:zoom_in_requested', () => {
          zoomIn()
        })
      )
      unsubscribers.push(
        viewBus.on('view:zoom_out_requested', () => {
          zoomOut()
        })
      )
      unsubscribers.push(
        viewBus.on('view:zoom_set_requested', ({ zoom }) => {
          const vp = getViewport()
          setViewport({ x: vp.x, y: vp.y, zoom }, { duration: ANIMATION.DURATION_FAST })
        })
      )
      return () => {
        unsubscribers.forEach((unsub) => unsub())
        unsubscribers.length = 0
      }
    }

    unsubscribers.push(
      eventBus.on('toolbar:export_requested', async ({ format, options }) => {
        // Worksheet headers only when the payload opts in (打印学习单 commit).
        const mergedOptions = mergeCanvasExportOptions(options)

        if (format === 'mg') {
          await canvasExportStore.runExportSession(async () => {
            await exportByFormat(format, mergedOptions)
          })
          return
        }

        if (format === 'community') {
          await canvasExportStore.runExportSession(async () => {
            await prepareForCommunityExport()
            showExportToCommunityModal.value = true
          })
          return
        }

        async function runFittedVisualExport<T>(run: () => Promise<T>): Promise<T> {
          const savedViewport = getViewport()
          fitApi.fitForExport()
          await nextTick()
          await waitForNextPaint()
          try {
            return await runWithExportVisualMode(uiStore, getExportContainer(), mergedOptions, run)
          } finally {
            setViewport(savedViewport, { duration: ANIMATION.DURATION_FAST })
          }
        }

        if (format === 'clipboard') {
          // Start clipboard.write in this turn (user gesture) with a Promise
          // that resolves after fit + color/B&W visual mode + PNG capture.
          const blobPromise = canvasExportStore.runExportSession(() =>
            runFittedVisualExport(() => capturePngBlob(mergedOptions, true))
          )
          await copyPngToClipboard(blobPromise)
          return
        }

        await canvasExportStore.runExportSession(() =>
          runFittedVisualExport(async () => {
            await exportByFormat(format, mergedOptions)
          })
        )
      })
    )

    unsubscribers.push(
      eventBus.on('toolbar:worksheet_text_requested', () => {
        canvasExportStore.openWorksheetTextModal()
      })
    )

    unsubscribers.push(
      viewBus.on('view:zoom_in_requested', () => {
        zoomIn()
      })
    )

    unsubscribers.push(
      viewBus.on('view:zoom_out_requested', () => {
        zoomOut()
      })
    )

    unsubscribers.push(
      viewBus.on('view:zoom_set_requested', ({ zoom }) => {
        const vp = getViewport()
        setViewport({ x: vp.x, y: vp.y, zoom }, { duration: ANIMATION.DURATION_FAST })
      })
    )

    let slideShowViewportSnapshot: { x: number; y: number; zoom: number } | null = null

    unsubscribers.push(
      viewBus.on('view:viewport_snapshot_save', () => {
        slideShowViewportSnapshot = getViewport()
      })
    )

    unsubscribers.push(
      viewBus.on('view:viewport_snapshot_restore', (data) => {
        if (!slideShowViewportSnapshot) return
        setViewport(slideShowViewportSnapshot, {
          duration: data?.animate === false ? 0 : (data?.duration ?? ANIMATION.DURATION_FAST),
        })
        slideShowViewportSnapshot = null
      })
    )

    unsubscribers.push(
      eventBus.on('node:text_updated', ({ nodeId, text }) => {
        if (isDiagramPresentationReadOnly() || sessionReadonly()) return
        const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
        const currentText = (node?.text ?? (node?.data as { label?: string })?.label ?? '').trim()
        const alreadyUpdated = currentText === text.trim()
        if (!alreadyUpdated) {
          diagramStore.updateNode(nodeId, { text })
          if (diagramStore.type === 'flow_map') {
            const spec = diagramStore.buildFlowMapSpecFromNodes()
            if (spec) {
              diagramStore.loadFromSpec(
                spec as Record<string, unknown>,
                'flow_map' as DiagramType,
                {
                  mergePreviousNodeStyles: true,
                }
              )
            }
          }
          diagramStore.pushHistory('Edit node text')
        }
        if (diagramStore.type === 'concept_map') {
          void nextTick(() => {
            if (diagramStore.data?.connections && diagramStore.data.nodes) {
              normalizeAllConceptMapTopicRootLabels(
                diagramStore.data.connections as Connection[],
                diagramStore.data.nodes as DiagramNode[]
              )
            }
            if (!alreadyUpdated) {
              regenerateForNodeIfNeeded(nodeId)
            }
          })
        }
        if (diagramStore.type === 'double_bubble_map') {
          scheduleDoubleBubbleRebuild(diagramStore)
        }
      })
    )

    unsubscribers.push(
      viewBus.on('multi_flow_map:topic_width_changed', ({ nodeId, width }) => {
        if (diagramStore.type !== 'multi_flow_map' || nodeId !== 'event' || width === null) {
          return
        }
        diagramStore.setTopicNodeWidth(width)
      })
    )

    unsubscribers.push(
      viewBus.on('multi_flow_map:node_width_changed', ({ nodeId, width }) => {
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
