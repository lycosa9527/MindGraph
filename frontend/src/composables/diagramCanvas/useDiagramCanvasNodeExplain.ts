import { computed, ref, watch, type Ref } from 'vue'

import {
  useNodeExplainBubblePosition,
  type ExplainBubbleSize,
} from '@/composables/canvasToolbar'
import { useMindMapNodeExplain } from '@/composables/mindMap/useMindMapNodeExplain'

type PositionedNode = {
  id: string
  position?: { x?: number; y?: number }
}

export function useDiagramCanvasNodeExplain(options: {
  canvasContainer: Ref<HTMLElement | null>
  nodes: Ref<PositionedNode[]>
  floatingToolbarAnchorId: Ref<string | null>
}) {
  const {
    visible: nodeExplainVisible,
    target: nodeExplainTarget,
    text: nodeExplainText,
    error: nodeExplainError,
    loading: nodeExplainLoading,
    openExplain: openNodeExplain,
    close: closeNodeExplain,
  } = useMindMapNodeExplain()

  const explainBubbleNodeId = computed(() => nodeExplainTarget.value?.nodeId ?? null)
  const explainBubbleSize = ref<ExplainBubbleSize | null>(null)
  const { position: explainBubblePosition, scheduleMeasure: scheduleExplainBubbleMeasure } =
    useNodeExplainBubblePosition({
      containerRef: options.canvasContainer,
      nodeId: explainBubbleNodeId,
      enabled: nodeExplainVisible,
      bubbleSize: explainBubbleSize,
    })

  function handleExplainBubbleSizeChange(size: ExplainBubbleSize | null): void {
    explainBubbleSize.value = size
  }

  function handleFloatingToolbarExplainNode(): void {
    const nodeId = options.floatingToolbarAnchorId.value
    if (!nodeId) return
    openNodeExplain(nodeId)
  }

  watch(
    () => {
      const nodeId = explainBubbleNodeId.value
      if (!nodeId || !nodeExplainVisible.value) return ''
      const node = options.nodes.value.find((item) => item.id === nodeId)
      return `${nodeId}:${node?.position?.x ?? 0}:${node?.position?.y ?? 0}`
    },
    () => {
      scheduleExplainBubbleMeasure()
    }
  )

  return {
    nodeExplainVisible,
    nodeExplainTarget,
    nodeExplainText,
    nodeExplainError,
    nodeExplainLoading,
    explainBubblePosition,
    closeNodeExplain,
    handleExplainBubbleSizeChange,
    handleFloatingToolbarExplainNode,
    scheduleExplainBubbleMeasure,
  }
}
