import { type Ref, computed, ref, watch } from 'vue'

import { type ExplainBubbleSize, useNodeExplainBubblePosition } from '@/composables/canvasToolbar'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useMindMapNodeExplain } from '@/composables/mindMap/useMindMapNodeExplain'
import { findExplainCenterNode } from '@/utils/mindMapExplainContext'
import { resolveExplainResearchSide } from '@/utils/mindMapExplainResearch'

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
    thinking: nodeExplainThinking,
    thinkingDone: nodeExplainThinkingDone,
    sources: nodeExplainSources,
    images: nodeExplainImages,
    error: nodeExplainError,
    loading: nodeExplainLoading,
    openExplain: openNodeExplain,
    close: closeNodeExplain,
  } = useMindMapNodeExplain()
  const diagramStore = useDiagramSession()

  const explainBubbleNodeId = computed(() => nodeExplainTarget.value?.nodeId ?? null)
  const nodeExplainResearchSide = computed(() => {
    const nodeId = explainBubbleNodeId.value
    if (!nodeId) return resolveExplainResearchSide(undefined, undefined)
    const node = options.nodes.value.find((item) => item.id === nodeId)
    const topic = findExplainCenterNode(options.nodes.value, diagramStore.type)
    return resolveExplainResearchSide(node?.position?.x, topic?.position?.x)
  })
  const nodeExplainPinned = ref(false)
  const explainBubbleSize = ref<ExplainBubbleSize | null>(null)
  const explainBubbleAnchored = computed(() => nodeExplainVisible.value && !nodeExplainPinned.value)
  const { position: explainBubblePosition, scheduleMeasure: scheduleExplainBubbleMeasure } =
    useNodeExplainBubblePosition({
      containerRef: options.canvasContainer,
      nodeId: explainBubbleNodeId,
      enabled: explainBubbleAnchored,
      bubbleSize: explainBubbleSize,
    })

  function handleExplainBubbleSizeChange(size: ExplainBubbleSize | null): void {
    explainBubbleSize.value = size
  }

  function handleCloseNodeExplain(): void {
    nodeExplainPinned.value = false
    closeNodeExplain()
  }

  watch(nodeExplainVisible, (open) => {
    if (!open) nodeExplainPinned.value = false
  })

  function openExplainOnCanvas(nodeId: string): void {
    const currentId = nodeExplainTarget.value?.nodeId
    if (nodeExplainPinned.value && currentId && currentId !== nodeId) {
      nodeExplainPinned.value = false
    }
    openNodeExplain(nodeId)
  }

  function handleFloatingToolbarExplainNode(): void {
    const nodeId = options.floatingToolbarAnchorId.value
    if (!nodeId) return
    openExplainOnCanvas(nodeId)
  }

  watch(
    () => {
      const nodeId = explainBubbleNodeId.value
      if (!nodeId || !nodeExplainVisible.value || nodeExplainPinned.value) return ''
      const node = options.nodes.value.find((item) => item.id === nodeId)
      return `${nodeId}:${node?.position?.x ?? 0}:${node?.position?.y ?? 0}`
    },
    () => {
      scheduleExplainBubbleMeasure()
    }
  )

  return {
    nodeExplainVisible,
    nodeExplainPinned,
    nodeExplainTarget,
    nodeExplainText,
    nodeExplainThinking,
    nodeExplainThinkingDone,
    nodeExplainSources,
    nodeExplainImages,
    nodeExplainResearchSide,
    nodeExplainError,
    nodeExplainLoading,
    explainBubblePosition,
    closeNodeExplain: handleCloseNodeExplain,
    handleExplainBubbleSizeChange,
    handleFloatingToolbarExplainNode,
    scheduleExplainBubbleMeasure,
    openNodeExplain: openExplainOnCanvas,
  }
}
