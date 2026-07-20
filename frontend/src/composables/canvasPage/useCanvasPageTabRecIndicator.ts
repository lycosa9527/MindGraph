/**
 * Drives the AI tab-rec visual indicator:
 *
 * - Normal mode (non-concept-map):
 *   green ant line on the NODE border  →  sets tabRecActive.
 *
 * - Concept maps: tab-rec green ant line is currently disabled (no node border,
 *   no edge overlay).  Inline recommendations still work; only the canvas hint is off.
 *
 * Two signals clear the indicator:
 *  1. activeNodeId → null  (canvas click, selection change, topic/diagram change)
 *  2. inline_recommendation:applied  (picker closes after a pick; activeNodeId is
 *     intentionally kept set by the store to allow multi-pick, so we mirror the
 *     picker's visual: once an option is applied the picker closes, ant line goes too)
 */
import { onUnmounted, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore } from '@/stores'
import { useCanvasNodeIndicatorsStore } from '@/stores/canvasNodeIndicators'
import { useInlineRecommendationsStore } from '@/stores/inlineRecommendations'

const TAB_REC_INDICATOR_OWNER = 'CanvasPageTabRecIndicator'

export function useCanvasPageTabRecIndicator(): void {
  const inlineRecStore = useInlineRecommendationsStore()
  const indicatorStore = useCanvasNodeIndicatorsStore()
  const diagramStore = useDiagramStore()

  // Track the node whose indicator is currently active so the applied-event
  // handler can clear indicators after a pick.
  let activeIndicatorNodeId: string | null = null

  function clearAll(): void {
    activeIndicatorNodeId = null
    indicatorStore.setTabRecActive(null)
    indicatorStore.setTabRecEdgeIds([])
  }

  // Primary signal: activeNodeId drives the indicator on/off.
  watch(
    () => inlineRecStore.activeNodeId,
    (nodeId) => {
      if (!nodeId) {
        clearAll()
        return
      }

      activeIndicatorNodeId = nodeId

      if (diagramStore.type === 'concept_map') {
        indicatorStore.setTabRecActive(null)
        indicatorStore.setTabRecEdgeIds([])
        return
      }

      // Normal mode: animate the node border.
      indicatorStore.setTabRecActive(nodeId)
      indicatorStore.setTabRecEdgeIds([])
    }
  )

  // Secondary signal: clear immediately when an option is applied.
  eventBus.onWithOwner(
    'inline_recommendation:applied',
    ({ nodeId }) => {
      if (activeIndicatorNodeId === nodeId) {
        clearAll()
      }
    },
    TAB_REC_INDICATOR_OWNER
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(TAB_REC_INDICATOR_OWNER)
    clearAll()
  })
}
