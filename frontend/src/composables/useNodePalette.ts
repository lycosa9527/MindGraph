/**
 * useNodePalette - Composable for Node Palette (瀑布流) AI-suggested nodes
 *
 * Handles:
 * - SSE streaming from /thinking_mode/node_palette/start and /next_batch
 * - Session management
 * - Multi-select and assembly to diagram
 *
 * Migrated from archive/static/js/editor/node-palette-manager.js
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { isPlaceholderText } from '@/composables/useAutoComplete'
import { eventBus } from '@/composables/useEventBus'
import { authFetch } from '@/utils/api'
import { useDiagramStore, usePanelsStore } from '@/stores'
import type { NodeSuggestion } from '@/types/panels'
import type { DiagramType } from '@/types'

const LEARNING_SHEET_PLACEHOLDER = '___'

function isNodePlaceholder(text: string | undefined): boolean {
  if (!text || !text.trim()) return false
  const t = text.trim()
  return t === LEARNING_SHEET_PLACEHOLDER || isPlaceholderText(t)
}

/**
 * Get placeholder content nodes for replacement, sorted by diagram slot order.
 */
function getPlaceholderNodes(
  diagramType: DiagramType | null,
  nodes: Array<{ id: string; text: string; type?: string }>,
  mode?: string | null,
  stage?: string | null
): Array<{ id: string; text: string }> {
  if (!diagramType || !nodes.length) return []

  const isPlaceholder = (n: { text: string }) => isNodePlaceholder(n.text)

  switch (diagramType) {
    case 'circle_map':
      return nodes
        .filter(
          (n) =>
            (n.type === 'bubble' || n.type === 'context') &&
            n.id.startsWith('context-') &&
            isPlaceholder(n)
        )
        .sort(
          (a, b) =>
            parseInt(a.id.replace('context-', ''), 10) -
            parseInt(b.id.replace('context-', ''), 10)
        )
    case 'bubble_map':
      return nodes
        .filter(
          (n) =>
            (n.type === 'bubble' || n.type === 'attribute') &&
            n.id.startsWith('bubble-') &&
            isPlaceholder(n)
        )
        .sort(
          (a, b) =>
            parseInt(a.id.replace('bubble-', ''), 10) -
            parseInt(b.id.replace('bubble-', ''), 10)
        )
    case 'multi_flow_map': {
      const slot = mode === 'effects' ? 'effect' : 'cause'
      return nodes
        .filter((n) => n.id.startsWith(`${slot}-`) && isPlaceholder(n))
        .sort(
          (a, b) =>
            parseInt(a.id.replace(`${slot}-`, ''), 10) -
            parseInt(b.id.replace(`${slot}-`, ''), 10)
        )
    }
    case 'double_bubble_map':
      if (mode === 'differences') {
        const leftNodes = nodes
          .filter((n) => /^left-diff-\d+$/.test(n.id) && isPlaceholder(n))
          .sort(
            (a, b) =>
              parseInt(a.id.replace('left-diff-', ''), 10) -
              parseInt(b.id.replace('left-diff-', ''), 10)
          )
        const rightNodes = nodes
          .filter((n) => /^right-diff-\d+$/.test(n.id) && isPlaceholder(n))
          .sort(
            (a, b) =>
              parseInt(a.id.replace('right-diff-', ''), 10) -
              parseInt(b.id.replace('right-diff-', ''), 10)
          )
        return leftNodes.map((l, i) => ({
          id: `${l.id}|${rightNodes[i]?.id ?? ''}`,
          text: l.text,
        }))
      }
      return nodes
        .filter((n) => /^similarity-\d+$/.test(n.id) && isPlaceholder(n))
        .sort(
          (a, b) =>
            parseInt(a.id.replace('similarity-', ''), 10) -
            parseInt(b.id.replace('similarity-', ''), 10)
        )
    case 'flow_map': {
      if (stage === 'substeps') {
        return nodes
          .filter((n) => n.id.startsWith('flow-substep-') && isPlaceholder(n))
          .sort((a, b) => a.id.localeCompare(b.id))
      }
      return nodes
        .filter((n) => n.id.startsWith('flow-step-') && isPlaceholder(n))
        .sort((a, b) => a.id.localeCompare(b.id))
    }
    case 'mindmap': {
      const firstLevelBranches = nodes.filter(
        (n) =>
          (n.id.startsWith('branch-l-1-') || n.id.startsWith('branch-r-1-')) &&
          isPlaceholder(n)
      )
      return firstLevelBranches.sort((a, b) => a.id.localeCompare(b.id))
    }
    case 'bridge_map': {
      if (stage === 'dimensions') {
        const dimNode = nodes.find((n) => n.id === 'dimension-label')
        if (dimNode && (!dimNode.text?.trim() || isPlaceholder(dimNode))) {
          return [{ id: 'dimension-label', text: dimNode.text ?? '' }]
        }
        return []
      }
      return nodes
        .filter((n) => /^pair-\d+-left$/.test(n.id) && isPlaceholder(n))
        .sort(
          (a, b) =>
            parseInt(a.id.replace('pair-', '').replace('-left', ''), 10) -
            parseInt(b.id.replace('pair-', '').replace('-left', ''), 10)
        )
    }
    case 'tree_map': {
      if (stage === 'dimensions') {
        const dimNode = nodes.find((n) => n.id === 'dimension-label')
        if (dimNode && (!dimNode.text?.trim() || isPlaceholder(dimNode))) {
          return [{ id: 'dimension-label', text: dimNode.text ?? '' }]
        }
        return []
      }
      if (stage === 'children') {
        return nodes
          .filter((n) => /^tree-leaf-\d+-\d+$/.test(n.id) && isPlaceholder(n))
          .sort((a, b) => a.id.localeCompare(b.id))
      }
      return nodes
        .filter((n) => /^tree-cat-\d+$/.test(n.id) && isPlaceholder(n))
        .sort(
          (a, b) =>
            parseInt(a.id.replace('tree-cat-', ''), 10) -
            parseInt(b.id.replace('tree-cat-', ''), 10)
        )
    }
    case 'brace_map': {
      if (stage === 'dimensions') {
        const dimNode = nodes.find((n) => n.id === 'dimension-label')
        if (dimNode && (!dimNode.text?.trim() || isPlaceholder(dimNode))) {
          return [{ id: 'dimension-label', text: dimNode.text ?? '' }]
        }
        return []
      }
      if (stage === 'subparts') {
        const subpartNodes = nodes.filter(
          (n) =>
            (n.id.startsWith('brace-subpart-') || /^brace-\d+-\d+$/.test(n.id)) &&
            n.type === 'brace' &&
            isPlaceholder(n)
        )
        return subpartNodes.sort((a, b) => a.id.localeCompare(b.id))
      }
      const partNodes = nodes.filter(
        (n) =>
          (n.id.startsWith('brace-part-') || /^brace-1-\d+$/.test(n.id)) &&
          n.type === 'brace' &&
          isPlaceholder(n)
      )
      return partNodes.sort((a, b) => a.id.localeCompare(b.id))
    }
    default:
      return []
  }
}

const NODE_PALETTE_START = '/thinking_mode/node_palette/start'
const NODE_PALETTE_NEXT = '/thinking_mode/node_palette/next_batch'

const STAGED_DIAGRAM_TYPES = [
  'mindmap',
  'flow_map',
  'tree_map',
  'brace_map',
  'bridge_map',
] as const

const DIMENSION_FIRST_TYPES = ['tree_map', 'brace_map', 'bridge_map'] as const

function hasDimension(
  diagramType: DiagramType | null,
  nodes: Array<{ id?: string; text?: string; type?: string }>,
  dataDimension?: string | null
): boolean {
  if (!DIMENSION_FIRST_TYPES.includes(diagramType as (typeof DIMENSION_FIRST_TYPES)[number])) {
    return true
  }
  const dim = dataDimension ?? nodes.find((n) => n.id === 'dimension-label')?.text ?? ''
  const t = (dim ?? '').trim()
  return t.length > 0 && !isPlaceholderText(t)
}

function getDefaultStage(
  diagramType: DiagramType | null,
  nodes: Array<{ id?: string; text?: string; type?: string }>,
  connections?: Array<{ source: string; target: string }>,
  dataDimension?: string | null
): string {
  switch (diagramType) {
    case 'mindmap':
      return 'branches'
    case 'flow_map':
      return 'steps'
    case 'tree_map': {
      if (!hasDimension(diagramType, nodes, dataDimension)) return 'dimensions'
      const hasCategories = nodes.some((n) => /^tree-cat-\d+$/.test(n.id ?? ''))
      return hasCategories ? 'children' : 'categories'
    }
    case 'brace_map': {
      if (!hasDimension(diagramType, nodes, dataDimension)) return 'dimensions'
      const rootId =
        nodes.find((n) => n.id === 'brace-whole' || n.id === 'brace-0-0')?.id ??
        nodes.find((n) => n.type === 'topic')?.id ??
        (connections
          ? nodes.find((n) => !new Set(connections.map((c) => c.target)).has(n.id ?? ''))?.id
          : undefined)
      const hasParts =
        rootId &&
        connections?.some((c) => c.source === rootId) &&
        nodes.some((n) => n.type === 'brace')
      return hasParts ? 'subparts' : 'parts'
    }
    case 'bridge_map': {
      if (!hasDimension(diagramType, nodes, dataDimension)) return 'dimensions'
      return 'pairs'
    }
    default:
      return 'branches'
  }
}

function stage2StageNameForType(dt: DiagramType | null): string {
  switch (dt) {
    case 'mindmap':
      return 'children'
    case 'flow_map':
      return 'substeps'
    case 'tree_map':
      return 'children'
    case 'brace_map':
      return 'subparts'
    case 'bridge_map':
      return 'pairs'
    default:
      return ''
  }
}

interface Stage2Parent {
  id: string
  name: string
}

function getStage2ParentsForDiagram(
  dt: DiagramType | null,
  nodes: Array<{ id?: string; text?: string; type?: string }>,
  connections?: Array<{ source: string; target: string }>
): Stage2Parent[] {
  const hasRealText = (n: { text?: string }) =>
    n.text && n.text.trim() && !isPlaceholderText(n.text)
  if (dt === 'mindmap') {
    return nodes
      .filter(
        (n) =>
          (n.id?.startsWith('branch-l-1-') || n.id?.startsWith('branch-r-1-')) &&
          hasRealText(n)
      )
      .map((n) => ({ id: n.id ?? '', name: String(n.text) }))
  }
  if (dt === 'flow_map') {
    return nodes
      .filter((n) => n.type === 'flow' && hasRealText(n))
      .map((n) => ({ id: n.id ?? '', name: String(n.text) }))
  }
  if (dt === 'tree_map') {
    return nodes
      .filter((n) => /^tree-cat-\d+$/.test(n.id ?? '') && hasRealText(n))
      .map((n) => ({ id: n.id ?? '', name: String(n.text) }))
  }
  if (dt === 'brace_map') {
    const targetIds = new Set(connections?.map((c) => c.target) ?? [])
    const rootId =
      nodes.find((n) => n.id === 'brace-whole' || n.id === 'brace-0-0')?.id ??
      nodes.find((n) => n.type === 'topic')?.id ??
      nodes.find((n) => !targetIds.has(n.id ?? ''))?.id
    return nodes
      .filter(
        (n) =>
          n.type === 'brace' &&
          connections?.some((c) => c.source === rootId && c.target === n.id) &&
          hasRealText(n)
      )
      .map((n) => ({ id: n.id ?? '', name: String(n.text) }))
  }
  return []
}

function buildStageDataForParent(
  parent: Stage2Parent,
  dt: DiagramType | null,
  extras?: { dimension?: string }
): Record<string, unknown> {
  const key =
    dt === 'mindmap'
      ? 'branch_name'
      : dt === 'flow_map'
        ? 'step_name'
        : dt === 'tree_map'
          ? 'category_name'
          : 'part_name'
  const data: Record<string, unknown> = { [key]: parent.name }
  if (dt === 'tree_map') {
    data.category_id = parent.id
  }
  if (dt === 'brace_map') {
    data.part_id = parent.id
    if (extras?.dimension?.trim()) {
      data.dimension = extras.dimension.trim()
    }
  }
  return data
}

export interface UseNodePaletteOptions {
  language?: 'en' | 'zh'
  onError?: (error: string) => void
}

/**
 * Build diagram_data for Node Palette API from current diagram
 */
function buildDiagramData(
  diagramType: DiagramType | null,
  nodes: Array<{ id: string; text: string; type?: string }>
): Record<string, unknown> {
  if (!diagramType || !nodes.length) {
    return { topic: '' }
  }

  const topicNode = nodes.find(
    (n) => n.type === 'topic' || n.type === 'center' || n.id === 'root'
  )
  const topicText = topicNode?.text?.trim() ?? ''

  switch (diagramType) {
    case 'circle_map': {
      const contextNodes = nodes.filter(
        (n) => (n.type === 'bubble' || n.type === 'context') && n.id.startsWith('context-')
      )
      return {
        topic: topicText,
        center: { text: topicText },
        context: contextNodes.map((n) => n.text),
      }
    }
    case 'bubble_map': {
      const attrNodes = nodes.filter(
        (n) => n.type === 'bubble' || n.type === 'attribute'
      )
      return {
        topic: topicText,
        center: { text: topicText },
        attributes: attrNodes.map((n) => ({ text: n.text })),
      }
    }
    case 'flow_map': {
      const flowTopic = nodes.find((n) => n.id === 'flow-topic')
      return {
        title: flowTopic?.text ?? topicText,
      }
    }
    case 'multi_flow_map': {
      const eventNode = nodes.find((n) => n.id === 'event')
      return {
        event: eventNode?.text ?? topicText,
      }
    }
    case 'double_bubble_map': {
      const leftNode = nodes.find((n) => n.id === 'left' || n.id?.includes('left'))
      const rightNode = nodes.find((n) => n.id === 'right' || n.id?.includes('right'))
      return {
        left: leftNode?.text ?? '',
        right: rightNode?.text ?? '',
      }
    }
    case 'brace_map': {
      const wholeNode = nodes.find(
        (n) =>
          n.id === 'brace-whole' ||
          n.id === 'brace-0-0' ||
          n.id === 'whole' ||
          n.type === 'whole'
      )
      const dimNode = nodes.find((n) => n.id === 'dimension-label')
      return {
        whole: wholeNode?.text ?? topicText,
        dimension: dimNode?.text ?? '',
      }
    }
    case 'bridge_map': {
      const dimNode = nodes.find(
        (n) => n.id === 'dimension-label' || n.id === 'dimension' || n.type === 'dimension'
      )
      return {
        dimension: dimNode?.text ?? '',
      }
    }
    case 'tree_map': {
      const dimNode = nodes.find((n) => n.id === 'dimension-label')
      return {
        topic: topicText,
        center: { text: topicText },
        dimension: dimNode?.text ?? '',
      }
    }
    case 'mindmap':
    default:
      return {
        topic: topicText,
        center: { text: topicText },
      }
  }
}

export function useNodePalette(options: UseNodePaletteOptions = {}) {
  const { language = 'en', onError } = options
  const diagramStore = useDiagramStore()
  const panelsStore = usePanelsStore()

  const sessionId = ref<string | null>(null)
  const centerTopic = ref('')
  const isLoading = ref(false)
  const isLoadingMore = ref(false)
  const errorMessage = ref<string | null>(null)
  const abortController = ref<AbortController | null>(null)

  const suggestions = computed(() => {
    const all = panelsStore.nodePalettePanel.suggestions
    const mode = panelsStore.nodePalettePanel.mode as string | null
    const dt = diagramStore.type
    if (dt === 'double_bubble_map' && mode) {
      return all.filter((s) => (s.mode ?? 'similarities') === mode)
    }
    if (
      (dt === 'mindmap' ||
        dt === 'flow_map' ||
        dt === 'tree_map' ||
        dt === 'brace_map' ||
        dt === 'bridge_map') &&
      mode
    ) {
      return all.filter((s) => (s.mode ?? '') === mode)
    }
    return all
  })
  const selectedIds = computed(() => panelsStore.nodePalettePanel.selected)
  const diagramType = computed(() => diagramStore.type)
  const isDimensionsStage = computed(() => {
    const stage = panelsStore.nodePalettePanel.stage
    const mode = panelsStore.nodePalettePanel.mode
    return stage === 'dimensions' || mode === 'dimensions'
  })
  const diagramData = computed(() => {
    const nodes = diagramStore.data?.nodes ?? []
    return buildDiagramData(diagramType.value, nodes)
  })

  /** Topic text for current diagram type (used for empty-check and streaming) */
  const topicText = computed(() => {
    const data = diagramData.value as Record<string, unknown>
    const topic = (data.topic as string) ?? ''
    const center = data.center as { text?: string } | undefined
    const title = (data.title as string) ?? ''
    const event = (data.event as string) ?? ''
    const whole = (data.whole as string) ?? ''
    const left = (data.left as string) ?? ''
    const right = (data.right as string) ?? ''
    const dimension = (data.dimension as string) ?? ''
    switch (diagramType.value) {
      case 'flow_map':
        return (title || topic || center?.text || '').trim()
      case 'multi_flow_map':
        return (event || topic || center?.text || '').trim()
      case 'double_bubble_map':
        return (left && right ? `${left} ${right}` : left || right || '').trim()
      case 'brace_map':
        return (whole || topic || center?.text || '').trim()
      case 'bridge_map':
        return (dimension || '').trim()
      default:
        return (topic || center?.text || '').trim()
    }
  })

  function generateSessionId(): string {
    return `palette_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
  }

  async function streamBatch(
    url: string,
    payload: Record<string, unknown>,
    isFirstBatch: boolean
  ): Promise<number> {
    const controller = new AbortController()
    abortController.value = controller

    const response = await authFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

    if (!response.ok) {
      const errText = await response.text()
      throw new Error(errText || `Request failed: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    const decoder = new TextDecoder()
    let nodeCount = 0
    const existingIds = new Set(panelsStore.nodePalettePanel.suggestions.map((s) => s.id))

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6)) as {
              event?: string
              node?: {
                id: string
                text: string
                type?: string
                source_llm?: string
              }
              error_type?: string
              message?: string
            }

            if (data.event === 'node_generated' && data.node) {
              const node = data.node as {
                id: string
                text: string
                type?: string
                source_llm?: string
                mode?: string
                left?: string
                right?: string
                dimension?: string
              }
              if (existingIds.has(node.id)) continue
              existingIds.add(node.id)
              nodeCount++

              panelsStore.setNodePaletteSuggestions([
                ...panelsStore.nodePalettePanel.suggestions,
                {
                  id: node.id,
                  text: node.text,
                  type: node.type ?? 'bubble',
                  source_llm: node.source_llm,
                  mode: node.mode,
                  left: node.left,
                  right: node.right,
                  dimension: node.dimension,
                },
              ])
            } else if (data.event === 'error') {
              const msg = data.message ?? 'Unknown error'
              errorMessage.value = msg
              onError?.(msg)
            } else if (data.event === 'batch_complete') {
              // Stream finished for this batch
            }
          } catch {
            // Skip malformed lines
          }
        }
      }
    } finally {
      abortController.value = null
    }

    return nodeCount
  }

  const isWaitingForTopicInput = ref(false)

  async function startSession(options?: { keepSessionId?: boolean }): Promise<boolean> {
    if (!diagramType.value || !diagramStore.data?.nodes?.length) {
      errorMessage.value = language === 'zh' ? '请先创建图示' : 'Please create a diagram first'
      return false
    }

    const topic = topicText.value
    const nodes = diagramStore.data?.nodes ?? []
    const connections = diagramStore.data?.connections
    const dataDimension = (diagramStore.data as Record<string, unknown>)?.dimension as
      | string
      | null
      | undefined
    const stage =
      panelsStore.nodePalettePanel.stage ??
      getDefaultStage(diagramType.value, nodes, connections, dataDimension)
    const isDimensionsStage = stage === 'dimensions'
    const canStartWithoutTopic =
      isDimensionsStage && diagramType.value === 'bridge_map'
    if (!canStartWithoutTopic && (!topic || !topic.trim())) {
      isWaitingForTopicInput.value = true
      errorMessage.value =
        language === 'zh' ? '请为主题节点输入文字' : 'Please enter text for the topic node'
      return false
    }
    if (
      !canStartWithoutTopic &&
      (isPlaceholderText(topic) || topic.trim() === LEARNING_SHEET_PLACEHOLDER)
    ) {
      isWaitingForTopicInput.value = true
      errorMessage.value =
        language === 'zh'
          ? '请输入真实主题，替换默认占位文字'
          : 'Please enter a real topic, replace the default placeholder'
      return false
    }

    const keepSessionId = options?.keepSessionId ?? false
    isWaitingForTopicInput.value = false
    if (!keepSessionId || !sessionId.value) {
      sessionId.value = generateSessionId()
    }
    centerTopic.value = topic
    errorMessage.value = null
    const dt = diagramType.value
    const isStaged = STAGED_DIAGRAM_TYPES.includes(dt as (typeof STAGED_DIAGRAM_TYPES)[number])
    const resolvedStage =
      panelsStore.nodePalettePanel.stage ??
      (isStaged ? stage : undefined)
    const stageData = panelsStore.nodePalettePanel.stage_data ?? undefined
    const mode =
      panelsStore.nodePalettePanel.mode ??
      (dt === 'double_bubble_map' ? 'similarities' : dt === 'multi_flow_map' ? 'causes' : resolvedStage)
    const paletteUpdates: {
      stage?: string
      stage_data?: Record<string, unknown> | null
      mode?: string
      selected: string[]
    } = { selected: [] }
    if (isStaged) {
      paletteUpdates.stage = resolvedStage
      paletteUpdates.stage_data = stageData ?? null
      paletteUpdates.mode = mode
    }
    if (keepSessionId) {
      panelsStore.updateNodePalette(paletteUpdates)
    } else {
      if (dt === 'double_bubble_map') {
        panelsStore.setNodePaletteSuggestions(
          panelsStore.nodePalettePanel.suggestions.filter((s) => (s.mode ?? 'similarities') !== mode)
        )
      } else if (isStaged) {
        panelsStore.setNodePaletteSuggestions(
          panelsStore.nodePalettePanel.suggestions.filter((s) => (s.mode ?? '') !== mode)
        )
      } else {
        panelsStore.setNodePaletteSuggestions([])
      }
      panelsStore.updateNodePalette(paletteUpdates)
    }

    isLoading.value = true
    try {
      const payload: Record<string, unknown> = {
        session_id: sessionId.value,
        diagram_type: dt,
        diagram_data: diagramData.value,
        language,
        mode,
      }
      if (isStaged && resolvedStage) {
        payload.stage = resolvedStage
        if (stageData && Object.keys(stageData).length > 0) {
          payload.stage_data = stageData
        }
      }
      await streamBatch(NODE_PALETTE_START, payload, true)
      return true
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      errorMessage.value = msg
      onError?.(msg)
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function loadNextBatch(): Promise<boolean> {
    const canLoadWithoutTopic =
      diagramType.value === 'bridge_map' &&
      (panelsStore.nodePalettePanel.stage === 'dimensions' ||
        getDefaultStage(
          diagramType.value,
          diagramStore.data?.nodes ?? [],
          diagramStore.data?.connections,
          (diagramStore.data as Record<string, unknown>)?.dimension as string | null | undefined
        ) === 'dimensions')
    if (
      !sessionId.value ||
      (!centerTopic.value && !canLoadWithoutTopic) ||
      isLoadingMore.value
    )
      return false

    isLoadingMore.value = true
    try {
      const dt = diagramType.value
      const isStaged = STAGED_DIAGRAM_TYPES.includes(dt as (typeof STAGED_DIAGRAM_TYPES)[number])
      const nodes = diagramStore.data?.nodes ?? []
      const connections = diagramStore.data?.connections
      const dataDimension = (diagramStore.data as Record<string, unknown>)?.dimension as
        | string
        | null
        | undefined
      const stage =
        panelsStore.nodePalettePanel.stage ??
        (isStaged ? getDefaultStage(dt, nodes, connections, dataDimension) : undefined)
      const stageData = panelsStore.nodePalettePanel.stage_data ?? undefined
      const mode =
        panelsStore.nodePalettePanel.mode ??
        (dt === 'double_bubble_map' ? 'similarities' : dt === 'multi_flow_map' ? 'causes' : stage)
      const payload: Record<string, unknown> = {
        session_id: sessionId.value,
        diagram_type: dt,
        center_topic: centerTopic.value,
        language,
        mode,
      }
      if (isStaged && stage) {
        payload.stage = stage
        if (stageData && Object.keys(stageData).length > 0) {
          payload.stage_data = stageData
        }
      }
      await streamBatch(NODE_PALETTE_NEXT, payload, false)
      return true
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      errorMessage.value = msg
      onError?.(msg)
      return false
    } finally {
      isLoadingMore.value = false
    }
  }

  function toggleSelection(nodeId: string): void {
    const stage = panelsStore.nodePalettePanel.stage ?? ''
    const singleSelect = stage === 'dimensions'
    panelsStore.toggleNodePaletteSelection(nodeId, singleSelect)
  }

  async function finishSelection(): Promise<boolean> {
    const selected = panelsStore.nodePalettePanel.selected
    const suggestionsList = panelsStore.nodePalettePanel.suggestions
    const stage = panelsStore.nodePalettePanel.stage ?? undefined
    const isDimensionsStage = stage === 'dimensions'
    const toApply = suggestionsList.filter((s) => selected.includes(s.id))

    if (toApply.length === 0) return false
    if (isDimensionsStage && toApply.length !== 1) return false

    diagramStore.pushHistory(language === 'zh' ? '替换/添加节点' : 'Replace/add nodes')

    const nodes = diagramStore.data?.nodes ?? []
    const diagramTypeVal = diagramType.value
    const stageData = panelsStore.nodePalettePanel.stage_data ?? undefined
    const mode =
      panelsStore.nodePalettePanel.mode ??
      (diagramTypeVal === 'double_bubble_map' ? 'similarities' : 'causes')

    const placeholders = getPlaceholderNodes(diagramTypeVal, nodes, mode, stage)
    let suggestionIndex = 0

    for (const slot of placeholders) {
      if (suggestionIndex >= toApply.length) break
      const suggestion = toApply[suggestionIndex]

      if (slot.id === 'dimension-label') {
        diagramStore.updateNode('dimension-label', { text: suggestion.text })
      } else if (diagramTypeVal === 'double_bubble_map' && mode === 'differences') {
        const ids = slot.id.split('|')
        const leftId = ids[0]
        const rightId = ids[1]
        const leftText =
          suggestion.left ?? suggestion.text.split('|').map((p) => p.trim())[0] ?? suggestion.text
        const rightText =
          suggestion.right ?? suggestion.text.split('|').map((p) => p.trim())[1] ?? ''
        if (leftId) diagramStore.updateNode(leftId, { text: leftText })
        if (rightId && rightText) diagramStore.updateNode(rightId, { text: rightText })
      } else if (diagramTypeVal === 'bridge_map' && /^pair-\d+-left$/.test(slot.id)) {
        const pairIndex = slot.id.replace('pair-', '').replace('-left', '')
        const rightId = `pair-${pairIndex}-right`
        const parts = suggestion.text.split('|').map((p) => p.trim())
        const leftText = parts[0] ?? suggestion.text
        const rightText = parts[1] ?? ''
        diagramStore.updateNode(slot.id, { text: leftText })
        diagramStore.updateNode(rightId, { text: rightText })
      } else {
        diagramStore.updateNode(slot.id, { text: suggestion.text })
      }
      suggestionIndex++
    }

    const remainder = toApply.slice(suggestionIndex)
    const isStaged = STAGED_DIAGRAM_TYPES.includes(
      diagramTypeVal as (typeof STAGED_DIAGRAM_TYPES)[number]
    )
    const isStage1WithParents =
      isStaged &&
      (stage === 'branches' ||
        stage === 'steps' ||
        stage === 'categories' ||
        stage === 'parts')
    if (remainder.length === 0 && !isDimensionsStage && !isStage1WithParents) {
      panelsStore.closeNodePalette()
      return true
    }
    if (isDimensionsStage && suggestionIndex > 0) {
      const selectedDimension = toApply[0]?.text ?? ''
      const nextStage =
        diagramTypeVal === 'tree_map'
          ? 'categories'
          : diagramTypeVal === 'brace_map'
            ? 'parts'
            : 'pairs'
      panelsStore.updateNodePalette({
        stage: nextStage,
        stage_data: { dimension: selectedDimension },
        mode: nextStage,
        selected: [],
      })
      await startSession({ keepSessionId: true })
      return false
    }
    if (remainder.length === 0 && isStage1WithParents) {
      const currentNodes = diagramStore.data?.nodes ?? []
      const parents = getStage2ParentsForDiagram(
        diagramTypeVal,
        currentNodes,
        diagramStore.data?.connections
      )
      if (parents.length > 0) {
        const dim =
          (stageData as { dimension?: string })?.dimension ??
          (diagramStore.data as { dimension?: string })?.dimension ??
          ''
        panelsStore.updateNodePalette({
          stage: stage2StageNameForType(diagramTypeVal),
          stage_data: buildStageDataForParent(parents[0], diagramTypeVal, {
            dimension: dim,
          }),
          mode: parents[0].name,
          selected: [],
        })
        return false
      }
      panelsStore.closeNodePalette()
      return true
    }

    if (diagramTypeVal === 'circle_map') {
      const contextNodes = nodes.filter((n) => n.id.startsWith('context-'))
      const nextIndex = contextNodes.length
      remainder.forEach((suggestion, i) => {
        diagramStore.addNode({
          id: `context-${nextIndex + i}`,
          text: suggestion.text,
          type: 'bubble',
          position: { x: 0, y: 0 },
          style: {},
        })
      })
    } else if (diagramTypeVal === 'bubble_map') {
      const bubbleNodes = nodes.filter(
        (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
      )
      const nextIndex = bubbleNodes.length
      const topicId = nodes.find((n) => n.type === 'topic' || n.type === 'center')?.id ?? 'topic'
      remainder.forEach((suggestion, i) => {
        const newId = `bubble-${nextIndex + i}`
        diagramStore.addNode({
          id: newId,
          text: suggestion.text,
          type: 'bubble',
          position: { x: 0, y: 0 },
          style: {},
        })
        diagramStore.addConnection(topicId, newId)
      })
    } else if (diagramTypeVal === 'multi_flow_map') {
      const category = mode === 'effects' ? 'effects' : 'causes'
      remainder.forEach((suggestion) => {
        diagramStore.addNode({
          id: `${category === 'effects' ? 'effect' : 'cause'}-temp`,
          text: suggestion.text,
          type: 'flow',
          position: { x: 0, y: 0 },
          style: {},
          category,
        } as Parameters<typeof diagramStore.addNode>[0] & { category?: string })
      })
    } else if (diagramTypeVal === 'double_bubble_map') {
      if (mode === 'differences') {
        remainder.forEach((suggestion) => {
          const leftText =
            suggestion.left ?? suggestion.text.split('|').map((p) => p.trim())[0] ?? suggestion.text
          const rightText =
            suggestion.right ?? suggestion.text.split('|').map((p) => p.trim())[1] ?? ''
          diagramStore.addDoubleBubbleMapNode('leftDiff', leftText, rightText)
        })
      } else {
        remainder.forEach((suggestion) => {
          diagramStore.addDoubleBubbleMapNode('similarity', suggestion.text)
        })
      }
    } else if (diagramTypeVal === 'mindmap') {
      if (stage === 'children' && stageData?.branch_name) {
        const parentId = nodes.find(
          (n) =>
            (n.id.startsWith('branch-l-') || n.id.startsWith('branch-r-')) &&
            n.text === stageData.branch_name
        )?.id
        if (parentId) {
          remainder.forEach((s) => diagramStore.addMindMapChild(parentId, s.text))
        }
      } else {
        remainder.forEach((s) =>
          diagramStore.addMindMapBranch('right', s.text, 'New Child')
        )
      }
    } else if (diagramTypeVal === 'flow_map') {
      if (stage === 'substeps' && stageData?.step_name) {
        remainder.forEach((s) =>
          diagramStore.addFlowMapSubstep(
            stageData.step_name as string,
            s.text
          )
        )
      } else {
        remainder.forEach((s) => diagramStore.addFlowMapStep(s.text))
      }
    } else if (diagramTypeVal === 'tree_map') {
      if (stage === 'children' && stageData?.category_name && stageData?.category_id) {
        remainder.forEach((s) =>
          diagramStore.addTreeMapChild(
            stageData.category_id as string,
            s.text
          )
        )
      } else {
        remainder.forEach((s) => diagramStore.addTreeMapCategory(s.text))
      }
    } else if (diagramTypeVal === 'brace_map') {
      const targetIds = new Set(diagramStore.data?.connections?.map((c) => c.target) ?? [])
      const wholeId =
        nodes.find((n) => n.id === 'brace-whole' || n.id === 'brace-0-0')?.id ??
        nodes.find((n) => n.type === 'topic')?.id ??
        nodes.find((n) => !targetIds.has(n.id))?.id
      if (stage === 'subparts' && stageData?.part_name && stageData?.part_id) {
        remainder.forEach((s) =>
          diagramStore.addBraceMapPart(stageData.part_id as string, s.text)
        )
      } else {
        remainder.forEach((s) =>
          diagramStore.addBraceMapPart(wholeId ?? 'topic', s.text)
        )
      }
    } else if (diagramTypeVal === 'bridge_map' && stage !== 'dimensions') {
      const pairNodes = nodes.filter(
        (n) =>
          (n as { data?: { pairIndex?: number } }).data?.pairIndex !== undefined &&
          !(n as { data?: { isDimensionLabel?: boolean } }).data?.isDimensionLabel
      )
      let maxPairIndex = -1
      pairNodes.forEach((n) => {
        const idx = (n as { data?: { pairIndex?: number } }).data?.pairIndex
        if (typeof idx === 'number' && idx > maxPairIndex) maxPairIndex = idx
      })
      const gapBetweenPairs = 50
      const verticalGap = 5
      const nodeWidth = 120
      const nodeHeight = 28
      const startX = 130
      let nextX = startX
      if (pairNodes.length > 0) {
        const rightmost = pairNodes.reduce((a, b) =>
          (a.position?.x ?? 0) > (b.position?.x ?? 0) ? a : b
        )
        nextX = (rightmost.position?.x ?? startX) + nodeWidth + gapBetweenPairs
      }
      const centerY = 300
      remainder.forEach((suggestion, i) => {
        const newPairIndex = maxPairIndex + 1 + i
        const parts = suggestion.text.split('|').map((p) => p.trim())
        const leftText =
          suggestion.left ?? parts[0] ?? suggestion.text
        const rightText = suggestion.right ?? parts[1] ?? ''
        const x = nextX + i * (nodeWidth + gapBetweenPairs)
        diagramStore.addNode({
          id: `pair-${newPairIndex}-left`,
          text: leftText,
          type: 'branch',
          position: { x, y: centerY - verticalGap - nodeHeight },
          data: {
            pairIndex: newPairIndex,
            position: 'left',
            diagramType: 'bridge_map',
          },
        })
        diagramStore.addNode({
          id: `pair-${newPairIndex}-right`,
          text: rightText,
          type: 'branch',
          position: { x, y: centerY + verticalGap },
          data: {
            pairIndex: newPairIndex,
            position: 'right',
            diagramType: 'bridge_map',
          },
        })
      })
    } else {
      const maxX = nodes.length
        ? Math.max(...nodes.map((n) => (n.position?.x ?? 0) + (n.style?.width ?? 120)))
        : 400
      remainder.forEach((suggestion, index) => {
        diagramStore.addNode({
          id: `node-${Date.now()}-${index}`,
          text: suggestion.text,
          type: 'bubble',
          position: { x: maxX + 20 + index * 30, y: 300 + index * 20 },
          style: {
            backgroundColor: '#ffffff',
            borderColor: '#4a90e2',
            textColor: '#303133',
          },
        })
      })
    }

    panelsStore.closeNodePalette()
    return true
  }

  function cancel(): void {
    if (abortController.value) {
      abortController.value.abort()
    }
    sessionId.value = null
    centerTopic.value = ''
    panelsStore.setNodePaletteSuggestions([])
    panelsStore.updateNodePalette({ selected: [] })
    panelsStore.closeNodePalette()
  }

  /**
   * Switch tab (for double_bubble_map: similarities | differences).
   * Preserves both modes' suggestions in same session. Only starts generation if target tab is empty.
   */
  async function switchTab(mode: 'similarities' | 'differences'): Promise<boolean> {
    if (diagramType.value !== 'double_bubble_map') return false
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    panelsStore.updateNodePalette({ mode, selected: [] })
    errorMessage.value = null
    const suggestionsForMode = panelsStore.nodePalettePanel.suggestions.filter(
      (s) => (s.mode ?? 'similarities') === mode
    )
    if (suggestionsForMode.length > 0) {
      return true
    }
    return startSession({ keepSessionId: true })
  }

  /**
   * Stage 2 parents for staged diagrams (branches, steps, categories, parts).
   */
  const stage2Parents = computed(() => {
    const dt = diagramType.value
    const nodes = diagramStore.data?.nodes ?? []
    if (dt === 'mindmap') {
      return nodes
        .filter(
          (n) =>
            (n.id.startsWith('branch-l-1-') || n.id.startsWith('branch-r-1-')) &&
            n.text
        )
        .map((n) => ({ id: n.id, name: String(n.text) }))
    }
    if (dt === 'flow_map') {
      return nodes
        .filter((n) => n.type === 'flow' && n.text)
        .map((n) => ({ id: n.id, name: String(n.text) }))
    }
    if (dt === 'tree_map') {
      return nodes
        .filter((n) => /^tree-cat-\d+$/.test(n.id ?? '') && n.text)
        .map((n) => ({ id: n.id ?? '', name: String(n.text) }))
    }
    if (dt === 'brace_map') {
      const targetIds = new Set(diagramStore.data?.connections?.map((c) => c.target) ?? [])
      const rootId =
        nodes.find((n) => n.id === 'brace-whole' || n.id === 'brace-0-0')?.id ??
        nodes.find((n) => n.type === 'topic')?.id ??
        nodes.find((n) => !targetIds.has(n.id))?.id
      return nodes
        .filter(
          (n) =>
            n.type === 'brace' &&
            diagramStore.data?.connections?.some(
              (c) => c.source === rootId && c.target === n.id
            )
        )
        .map((n) => ({ id: n.id ?? '', name: String(n.text) }))
    }
    return []
  })

  const isStagedDiagram = computed(() =>
    STAGED_DIAGRAM_TYPES.includes(diagramType.value as (typeof STAGED_DIAGRAM_TYPES)[number])
  )

  const defaultStage = computed(() => {
    const dt = diagramType.value
    const nodes = diagramStore.data?.nodes ?? []
    const connections = diagramStore.data?.connections
    const dataDimension = (diagramStore.data as Record<string, unknown>)?.dimension as
      | string
      | null
      | undefined
    return getDefaultStage(dt, nodes, connections, dataDimension)
  })

  const stage2StageName = computed(() => {
    switch (diagramType.value) {
      case 'mindmap':
        return 'children'
      case 'flow_map':
        return 'substeps'
      case 'tree_map':
        return 'children'
      case 'brace_map':
        return 'subparts'
      default:
        return ''
    }
  })

  /**
   * Switch to a stage 2 parent tab (e.g. branch, step, category, part).
   */
  async function switchStageTab(parentId: string, parentName: string): Promise<boolean> {
    if (!isStagedDiagram.value) return false
    const dt = diagramType.value
    const stageName = stage2StageName.value
    if (!stageName) return false
    const stageDataKey =
      dt === 'mindmap'
        ? 'branch_name'
        : dt === 'flow_map'
          ? 'step_name'
          : dt === 'tree_map'
            ? 'category_name'
            : 'part_name'
    const stageDataIdKey =
      dt === 'tree_map' ? 'category_id' : dt === 'brace_map' ? 'part_id' : undefined
    const stageData: Record<string, unknown> = { [stageDataKey]: parentName }
    if (stageDataIdKey) {
      stageData[stageDataIdKey] = parentId
    }
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    panelsStore.updateNodePalette({
      stage: stageName,
      stage_data: stageData,
      mode: parentName,
      selected: [],
    })
    errorMessage.value = null
    const suggestionsForMode = panelsStore.nodePalettePanel.suggestions.filter(
      (s) => (s.mode ?? '') === parentName
    )
    if (suggestionsForMode.length > 0) {
      return true
    }
    return startSession({ keepSessionId: true })
  }

  watch(
    () => panelsStore.nodePalettePanel.isOpen,
    (isOpen) => {
      if (!isOpen) {
        sessionId.value = null
        isWaitingForTopicInput.value = false
      }
    }
  )

  watch(
    () => topicText.value,
    (newTopic, oldTopic) => {
      const wasEmpty = !oldTopic || oldTopic.length === 0
      const nowHasContent = newTopic && newTopic.length > 0
      if (
        wasEmpty &&
        nowHasContent &&
        panelsStore.nodePalettePanel.isOpen &&
        isWaitingForTopicInput.value &&
        !isLoading.value
      ) {
        startSession()
      }
    }
  )

  function resetSessionState(): void {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    sessionId.value = null
    centerTopic.value = ''
    errorMessage.value = null
    isWaitingForTopicInput.value = false
  }

  eventBus.onWithOwner('diagram:loaded', resetSessionState, 'useNodePalette')
  eventBus.onWithOwner('diagram:type_changed', resetSessionState, 'useNodePalette')

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner('useNodePalette')
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
  })

  /** For double_bubble_map: { left, right } topic labels for display */
  const doubleBubbleTopics = computed(() => {
    if (diagramType.value !== 'double_bubble_map') return null
    const data = diagramData.value as { left?: string; right?: string }
    const fallbackLeft = language === 'zh' ? '主题A' : 'Topic A'
    const fallbackRight = language === 'zh' ? '主题B' : 'Topic B'
    return {
      left: (data.left ?? '').trim() || fallbackLeft,
      right: (data.right ?? '').trim() || fallbackRight,
    }
  })

  function getStageDataForParent(parent: { id: string; name: string }): Record<string, unknown> {
    const dim =
      (diagramData.value as { dimension?: string })?.dimension ??
      (panelsStore.nodePalettePanel.stage_data as { dimension?: string })?.dimension ??
      ''
    return buildStageDataForParent(parent, diagramType.value, { dimension: dim })
  }

  return {
    sessionId,
    centerTopic,
    isLoading,
    isLoadingMore,
    errorMessage,
    suggestions,
    selectedIds,
    diagramType,
    doubleBubbleTopics,
    isStagedDiagram,
    isDimensionsStage,
    stage2Parents,
    stage2StageName,
    defaultStage,
    getStageDataForParent,
    startSession,
    loadNextBatch,
    toggleSelection,
    finishSelection,
    cancel,
    switchTab,
    switchStageTab,
  }
}
