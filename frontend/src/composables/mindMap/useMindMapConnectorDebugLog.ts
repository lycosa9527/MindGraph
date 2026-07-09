import { nextTick, watch, type Ref } from 'vue'

import { storeToRefs } from 'pinia'

import { useDiagramStore } from '@/stores'
import type { MindGraphEdge, MindGraphNode, MindGraphNodeData } from '@/types'
import { dumpMindMapConnectorDebug } from '@/utils/mindMapConnectorDebug'
import { isMindMapConnectorVerboseDebugEnabled } from '@/utils/mindMapConnectorDebugLevel'
import { setMindMapVerboseRecalcGen } from '@/utils/mindMapConnectorDebugVerbose'

/** Wait for layout recalc + vue-flow paint before dumping positions (read-only). */
const MIND_MAP_LAYOUT_SETTLE_MS = 100

/**
 * After layout settles, dump node/connector positions to the console.
 * Read-only — does not measure anchors into Pinia or trigger recalc.
 *
 * Opt-in: localStorage mindgraph.debugMindMapConnectors = '1' | 'verbose', or window.mindMapConnectorDebug in dev.
 */
export function useMindMapConnectorDebugLog(options: {
  enabled: Ref<boolean>
  containerRef: Ref<HTMLElement | null>
  screenToFlowCoordinate: (pos: { x: number; y: number }) => { x: number; y: number }
}): void {
  const diagramStore = useDiagramStore()
  const { mindMapRecalcTrigger } = storeToRefs(diagramStore)

  function readRecalcGeneration(): number {
    return mindMapRecalcTrigger?.value ?? 0
  }

  let rafId = 0
  let settleTimer: ReturnType<typeof setTimeout> | null = null

  function scheduleDump(): void {
    if (!options.enabled.value) return
    if (settleTimer != null) {
      clearTimeout(settleTimer)
    }
    settleTimer = setTimeout(() => {
      settleTimer = null
      if (rafId !== 0 && typeof cancelAnimationFrame === 'function') {
        cancelAnimationFrame(rafId)
      }
      rafId = requestAnimationFrame(() => {
        rafId = 0
        nextTick(() => {
          requestAnimationFrame(() => {
            const data = diagramStore.data
            if (!data?.nodes?.length) return

            const flowNodes = diagramStore.vueFlowNodes.map((node) => {
              const graphNode = node as MindGraphNode & {
                dimensions?: { width?: number; height?: number }
              }
              return {
                id: graphNode.id,
                position: graphNode.position,
                dimensions: graphNode.dimensions,
                data: graphNode.data as {
                  estimatedWidth?: number
                  estimatedHeight?: number
                  style?: import('@/types').NodeStyle
                },
              }
            })
            const flowEdges = diagramStore.vueFlowEdges.map((edge) => {
              const graphEdge = edge as MindGraphEdge & {
                sourceX?: number
                sourceY?: number
                targetX?: number
                targetY?: number
              }
              return {
                id: graphEdge.id,
                source: graphEdge.source,
                target: graphEdge.target,
                sourceX: graphEdge.sourceX,
                sourceY: graphEdge.sourceY,
                targetX: graphEdge.targetX,
                targetY: graphEdge.targetY,
              }
            })

            dumpMindMapConnectorDebug({
              container: options.containerRef.value,
              diagramNodes: data.nodes,
              flowNodes,
              edges: flowEdges,
              widths: diagramStore.mindMapNodeWidths as Record<string, number>,
              heights: diagramStore.mindMapNodeHeights as Record<string, number>,
              preservedNodeStyles: (data._node_styles ?? {}) as Record<
                string,
                import('@/types').NodeStyle
              >,
              diagramStyleId: data._mindmap_diagram_style as string | undefined,
              recalcGeneration: readRecalcGeneration(),
              screenToFlowCoordinate: options.screenToFlowCoordinate,
            })
          })
        })
      })
    }, MIND_MAP_LAYOUT_SETTLE_MS)
  }

  watch(
    () => readRecalcGeneration(),
    () => {
      if (isMindMapConnectorVerboseDebugEnabled()) {
        setMindMapVerboseRecalcGen(readRecalcGeneration())
      }
      scheduleDump()
    },
    { immediate: true }
  )
}
