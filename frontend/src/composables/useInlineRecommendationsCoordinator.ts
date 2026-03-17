/**
 * useInlineRecommendationsCoordinator - Central event handler for inline recommendations
 *
 * Subscribes to node:text_updated, paneClick, diagram changes, etc.
 * Dispatches to store actions. Call setup() in CanvasPage onMounted, teardown() onUnmounted.
 */
import { onUnmounted, watch } from 'vue'

import { useAutoComplete } from '@/composables/useAutoComplete'
import { eventBus } from '@/composables/useEventBus'
import { INLINE_RECOMMENDATIONS_SUPPORTED_TYPES } from '@/composables/nodePalette/constants'
import { useDiagramStore, useInlineRecommendationsStore } from '@/stores'

const TOPIC_NODE_IDS = new Set([
  'topic',
  'center',
  'root',
  'flow-topic',
  'tree-topic',
  'brace-whole',
  'brace-0-0',
  'whole',
  'left-topic',
  'right-topic',
  'event',
  'dimension-label',
])

function isTopicNode(nodeId: string | undefined, diagramType: string): boolean {
  if (!nodeId) return false
  if (TOPIC_NODE_IDS.has(nodeId)) return true
  if (diagramType === 'brace_map' && nodeId === 'dimension-label') return false
  return false
}

const DEBOUNCE_MS = 300

export function useInlineRecommendationsCoordinator() {
  const diagramStore = useDiagramStore()
  const store = useInlineRecommendationsStore()
  const {
    extractMainTopic,
    isPlaceholderText,
    extractFixedDimension,
    extractBridgeMapAnalogies,
  } = useAutoComplete()

  let topicDebounceTimer: ReturnType<typeof setTimeout> | null = null

  function getTopicFromDiagram(): string {
    return extractMainTopic() ?? ''
  }

  function revalidateReady(): void {
    const topic = getTopicFromDiagram()
    const dt = diagramStore.type
    const normalizedDt = dt === 'mind_map' ? 'mindmap' : dt
    let topicValid =
      topic.trim().length > 0 &&
      !isPlaceholderText(topic) &&
      (INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(
        normalizedDt ?? ''
      )
    if (
      !topicValid &&
      normalizedDt === 'tree_map' &&
      diagramStore.data?.nodes
    ) {
      const dimNode = diagramStore.data.nodes.find(
        (n: { id?: string; text?: string }) => n.id === 'dimension-label'
      )
      const dimText = (dimNode?.text ?? '').trim()
      topicValid =
        dimText.length > 0 &&
        !isPlaceholderText(dimText) &&
        (INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(
          normalizedDt ?? ''
        )
    }
    if (
      !topicValid &&
      normalizedDt === 'bridge_map'
    ) {
      const dimension = extractFixedDimension()
      const analogies = extractBridgeMapAnalogies()
      const hasDimension = (dimension ?? '').trim().length > 0 && !isPlaceholderText(dimension ?? '')
      const hasFirstPair = analogies.length > 0
      topicValid =
        hasDimension &&
        hasFirstPair &&
        (INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(
          normalizedDt ?? ''
        )
    }
    if (
      topicValid &&
      normalizedDt === 'double_bubble_map' &&
      diagramStore.data?.nodes
    ) {
      const nodes = diagramStore.data.nodes as Array<{ id?: string; text?: string }>
      const leftNode = nodes.find((n) => n.id === 'left-topic')
      const rightNode = nodes.find((n) => n.id === 'right-topic')
      const getText = (n: { id?: string; text?: string } | undefined) =>
        (n?.text ?? '').trim()
      const leftValid = getText(leftNode).length > 0 && !isPlaceholderText(getText(leftNode))
      const rightValid =
        getText(rightNode).length > 0 && !isPlaceholderText(getText(rightNode))
      topicValid = leftValid && rightValid
    }
    store.onTopicUpdated(topic, topicValid)
  }

  function onTopicNodeUpdated(_topic: string): void {
    if (topicDebounceTimer) clearTimeout(topicDebounceTimer)
    topicDebounceTimer = setTimeout(() => {
      topicDebounceTimer = null
      revalidateReady()
    }, DEBOUNCE_MS)
  }

  function onOtherNodeUpdated(_nodeId: string): void {
    const activeId = store.activeNodeId
    if (!activeId) return
    const hasOptions = (store.options[activeId]?.length ?? 0) > 0
    const isGenerating = store.generatingNodeIds.has(activeId)
    // Don't invalidate while streaming: Tab blur emits text_updated; we must keep accumulating
    if (hasOptions && !isGenerating) {
      store.invalidateForNode(activeId)
    }
  }

  function onDiagramChanged(): void {
    store.invalidateAll()
    revalidateReady()
  }

  function onDismiss(): void {
    store.invalidateAll()
  }

  function onSelectionChanged(selectedNodes: string[]): void {
    const activeId = store.activeNodeId
    if (!activeId) return
    const selectedSet = new Set(selectedNodes)
    if (!selectedSet.has(activeId)) {
      store.invalidateAll()
    }
  }

  const unsubNodeText = eventBus.on(
    'node:text_updated',
    ({ nodeId, text }: { nodeId: string; text: string }) => {
      const dt = diagramStore.type
      const normalizedDt = dt === 'mind_map' ? 'mindmap' : dt
      if (
        !(INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(
          normalizedDt ?? ''
        )
      )
        return

      if (isTopicNode(nodeId, normalizedDt ?? '')) {
        onTopicNodeUpdated(text)
      } else {
        onOtherNodeUpdated(nodeId)
      }
    }
  )

  const unsubPaneClick = eventBus.on('canvas:pane_clicked', () => {
    onDismiss()
  })

  const unsubSelectionChanged = eventBus.on(
    'state:selection_changed',
    ({ selectedNodes }: { selectedNodes: string[] }) => {
      onSelectionChanged(selectedNodes ?? [])
    }
  )

  const unsubDiagramType = eventBus.on('diagram:type_changed', () => {
    onDiagramChanged()
  })

  const unsubDiagramLoaded = eventBus.on('diagram:loaded', () => {
    onDiagramChanged()
  })

  watch(
    () => diagramStore.data,
    () => revalidateReady(),
    { immediate: true }
  )

  function setup(): void {
    revalidateReady()
  }

  function teardown(): void {
    unsubNodeText()
    unsubPaneClick()
    unsubSelectionChanged()
    unsubDiagramType()
    unsubDiagramLoaded()
    if (topicDebounceTimer) {
      clearTimeout(topicDebounceTimer)
      topicDebounceTimer = null
    }
    store.invalidateAll()
  }

  onUnmounted(() => {
    teardown()
  })

  return { setup, teardown, revalidateReady }
}
