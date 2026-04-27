/**
 * useInlineRecommendationsCoordinator - Central event handler for inline recommendations (Tab mode)
 *
 * Supported types: INLINE_RECOMMENDATIONS_SUPPORTED_TYPES (mindmap, flow_map, tree_map, brace_map,
 * circle_map, bubble_map, double_bubble_map, multi_flow_map, bridge_map, concept_map).
 *
 * Behaviour (consistent across types):
 * - `canvas:pane_clicked` (mouse on pane or mobile tap): concept-map relationship store clearAll
 *   (aborts label SSE) + inline rec invalidateAll (aborts Tab SSE) + clearSelection — same
 *   whether triggered from useDiagramCanvasContextMenu or useDiagramCanvasMobileTouch.
 * - Clears inline rec only: topic hash change; `onDiagramChanged` (diagram type / diagram:loaded);
 *   teardown; selection change that no longer “covers” the active Tab session; relationship clear
 *   is included on `onDiagramChanged` and teardown to avoid stale label pickers.
 * - Keeps options after applying a numeric pick: node:text_updated does not clear (pair updates
 *   emit twice for bridge + double bubble — still OK).
 * - Double bubble layout refresh uses loadFromSpec(..., { emitLoaded: false }) so it does not
 *   masquerade as a full load.
 * - Selection: dismiss when the active session node is no longer selected; for bridge + double
 *   bubble difference pairs, the opposite paired node still counts as “same row” context.
 */
import { onUnmounted, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useAutoComplete } from '@/composables/editor/useAutoComplete'
import { INLINE_RECOMMENDATIONS_SUPPORTED_TYPES } from '@/composables/nodePalette/constants'
import { useDiagramStore, useInlineRecommendationsStore } from '@/stores'
import { useConceptMapRelationshipStore } from '@/stores/conceptMapRelationship'

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

/** Bridge / double-bubble: Tab session is for one “row”; selection on the paired node is still that row. */
function selectionStillCoversInlineActive(
  activeId: string,
  selectedNodes: string[],
  diagramType: string | null
): boolean {
  const selected = new Set(selectedNodes)
  if (selected.has(activeId)) return true
  const dt = diagramType === 'mind_map' ? 'mindmap' : diagramType
  if (dt === 'double_bubble_map') {
    const leftM = activeId.match(/^left-diff-(\d+)$/)
    const rightM = activeId.match(/^right-diff-(\d+)$/)
    if (leftM?.[1] && selected.has(`right-diff-${leftM[1]}`)) return true
    if (rightM?.[1] && selected.has(`left-diff-${rightM[1]}`)) return true
  }
  if (dt === 'bridge_map') {
    const leftM = activeId.match(/^pair-(\d+)-left$/)
    const rightM = activeId.match(/^pair-(\d+)-right$/)
    if (leftM?.[1] && selected.has(`pair-${leftM[1]}-right`)) return true
    if (rightM?.[1] && selected.has(`pair-${rightM[1]}-left`)) return true
  }
  return false
}

export function useInlineRecommendationsCoordinator() {
  const diagramStore = useDiagramStore()
  const store = useInlineRecommendationsStore()
  const relationshipStore = useConceptMapRelationshipStore()
  const { extractMainTopic, isPlaceholderText, extractFixedDimension, extractBridgeMapAnalogies } =
    useAutoComplete()

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
      (INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(normalizedDt ?? '')
    if (!topicValid && normalizedDt === 'tree_map' && diagramStore.data?.nodes) {
      const dimNode = diagramStore.data.nodes.find(
        (n: { id?: string; text?: string }) => n.id === 'dimension-label'
      )
      const dimText = (dimNode?.text ?? '').trim()
      topicValid =
        dimText.length > 0 &&
        !isPlaceholderText(dimText) &&
        (INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(normalizedDt ?? '')
    }
    if (!topicValid && normalizedDt === 'bridge_map') {
      const dimension = extractFixedDimension()
      const analogies = extractBridgeMapAnalogies()
      const hasDimension =
        (dimension ?? '').trim().length > 0 && !isPlaceholderText(dimension ?? '')
      const hasFirstPair = analogies.length > 0
      topicValid =
        hasDimension &&
        hasFirstPair &&
        (INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(normalizedDt ?? '')
    }
    if (topicValid && normalizedDt === 'double_bubble_map' && diagramStore.data?.nodes) {
      const nodes = diagramStore.data.nodes as Array<{ id?: string; text?: string }>
      const leftNode = nodes.find((n) => n.id === 'left-topic')
      const rightNode = nodes.find((n) => n.id === 'right-topic')
      const getText = (n: { id?: string; text?: string } | undefined) => (n?.text ?? '').trim()
      const leftValid = getText(leftNode).length > 0 && !isPlaceholderText(getText(leftNode))
      const rightValid = getText(rightNode).length > 0 && !isPlaceholderText(getText(rightNode))
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

  function onDiagramChanged(): void {
    relationshipStore.clearAll()
    store.invalidateAll()
    revalidateReady()
  }

  /**
   * Single handler for background tap (mouse or mobile synthetic): match desktop pane click —
   * abort relationship label streams, abort/clear Tab inline rec SSE, then clear selection.
   * Order: clear transient stores before selection so selection_changed does not re-fire inline.
   */
  function onCanvasPaneClicked(): void {
    relationshipStore.clearAll()
    store.invalidateAll()
    diagramStore.clearSelection()
  }

  function onSelectionChanged(selectedNodes: string[]): void {
    const activeId = store.activeNodeId
    if (!activeId) return
    if (selectionStillCoversInlineActive(activeId, selectedNodes, diagramStore.type)) return
    store.invalidateAll()
  }

  const unsubNodeText = eventBus.on(
    'node:text_updated',
    ({ nodeId, text }: { nodeId: string; text: string }) => {
      const dt = diagramStore.type
      const normalizedDt = dt === 'mind_map' ? 'mindmap' : dt
      if (
        !(INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(normalizedDt ?? '')
      )
        return

      if (isTopicNode(nodeId, normalizedDt ?? '')) {
        onTopicNodeUpdated(text)
      }
      // Non-topic node:text_updated (e.g. applying a Tab recommendation) must NOT clear inline
      // recs — users may pick another option. Dismiss via pane click, selection change, or topic.
    }
  )

  const unsubPaneClick = eventBus.on('canvas:pane_clicked', () => {
    onCanvasPaneClicked()
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
    relationshipStore.clearAll()
    store.reset()
  }

  onUnmounted(() => {
    teardown()
  })

  return { setup, teardown, revalidateReady }
}
