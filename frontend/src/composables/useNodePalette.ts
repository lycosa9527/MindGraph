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
import { useRoute } from 'vue-router'

import { isPlaceholderText } from '@/composables/useAutoComplete'
import { eventBus } from '@/composables/useEventBus'
import { useDiagramStore, usePanelsStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import { authFetch } from '@/utils/api'

import { applySelectionToDiagram } from './nodePalette/applySelection'
import {
  getParentIdFromStageData,
  LEARNING_SHEET_PLACEHOLDER,
  NODE_PALETTE_NEXT,
  NODE_PALETTE_START,
  STAGED_DIAGRAM_TYPES,
  suggestionBelongsToParent,
} from './nodePalette/constants'
import { buildDiagramData } from './nodePalette/diagramDataBuilder'
import {
  type Stage2Parent,
  buildStageDataForParent,
  getDefaultStage,
  getStage2ParentsForDiagram,
  stage2StageNameForType,
} from './nodePalette/stageHelpers'

function isAbortError(err: unknown): boolean {
  if (err instanceof Error) {
    if (err.name === 'AbortError') return true
    const msg = err.message.toLowerCase()
    return msg.includes('aborted') || msg.includes('bodystream')
  }
  return false
}

export interface UseNodePaletteOptions {
  language?: 'en' | 'zh'
  onError?: (error: string) => void
  /** When true, clears singleton on unmount (used by getNodePalette) */
  _asSingleton?: boolean
}

function getNodePaletteDiagramKey(
  diagramType: string,
  activeDiagramId: string | null,
  routeDiagramId: string | undefined
): string {
  const id = routeDiagramId || activeDiagramId || 'new'
  return `${diagramType}-${id}`
}

let _nodePaletteInstance: ReturnType<typeof useNodePalette> | null = null

export function getNodePalette(options: UseNodePaletteOptions = {}) {
  if (!_nodePaletteInstance) {
    _nodePaletteInstance = useNodePalette({ ...options, _asSingleton: true })
  }
  return _nodePaletteInstance
}

export function useNodePalette(options: UseNodePaletteOptions = {}) {
  const { language = 'en', onError, _asSingleton } = options
  const route = useRoute()
  const diagramStore = useDiagramStore()
  const panelsStore = usePanelsStore()
  const savedDiagramsStore = useSavedDiagramsStore()

  const sessionId = ref<string | null>(null)
  const centerTopic = ref('')
  const isLoading = ref(false)
  const isLoadingMore = ref(false)
  const errorMessage = ref<string | null>(null)
  const abortController = ref<AbortController | null>(null)

  const rawDiagramType = computed(() => diagramStore.type)
  const diagramType = computed(() => {
    const dt = rawDiagramType.value
    return dt === 'mind_map' ? 'mindmap' : dt
  })

  const suggestions = computed(() => {
    const all = panelsStore.nodePalettePanel.suggestions
    const mode = panelsStore.nodePalettePanel.mode as string | null
    const stage = panelsStore.nodePalettePanel.stage
    const stageData = panelsStore.nodePalettePanel.stage_data
    const dt = diagramType.value
    if (dt === 'double_bubble_map' && mode) {
      return all.filter((s) => (s.mode ?? 'similarities') === mode)
    }
    if (dt === 'multi_flow_map' && mode) {
      return all.filter((s) => (s.mode ?? 'causes') === mode)
    }
    if (
      (dt === 'mindmap' ||
        dt === 'flow_map' ||
        dt === 'tree_map' ||
        dt === 'brace_map' ||
        dt === 'bridge_map') &&
      mode
    ) {
      const parentId = getParentIdFromStageData(
        dt ?? '',
        stage ?? undefined,
        (stageData ?? undefined) as Record<string, unknown>
      )
      return all.filter((s) => {
        if (parentId && s.parent_id) return s.parent_id === parentId
        return (s.mode ?? '') === mode
      })
    }
    return all
  })
  const selectedIds = computed(() => panelsStore.nodePalettePanel.selected)
  const isDimensionsStage = computed(() => {
    const stage = panelsStore.nodePalettePanel.stage
    const mode = panelsStore.nodePalettePanel.mode
    return stage === 'dimensions' || mode === 'dimensions'
  })

  const isStage1WithNext = computed(() => {
    const stage = panelsStore.nodePalettePanel.stage ?? ''
    const dt = diagramType.value
    if (dt === 'mindmap') return stage === 'branches'
    if (dt === 'flow_map') return stage === 'steps'
    if (dt === 'tree_map') return stage === 'categories'
    if (dt === 'brace_map') return stage === 'parts'
    return false
  })

  const showNextButton = computed(() => isDimensionsStage.value || isStage1WithNext.value)
  const diagramData = computed(() => {
    const nodes = diagramStore.data?.nodes ?? []
    return buildDiagramData(diagramType.value, nodes)
  })

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
      case 'concept_map':
        return (topic || center?.text || '').trim()
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
    options?: {
      append?: boolean
      sharedExistingIds?: Set<string>
      useGlobalAbort?: boolean
    }
  ): Promise<number> {
    const useGlobalAbort = options?.useGlobalAbort !== false
    const controller = new AbortController()
    if (useGlobalAbort) {
      abortController.value = controller
    }

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
    const existingIds =
      options?.sharedExistingIds ??
      new Set(panelsStore.nodePalettePanel.suggestions.map((s) => s.id))
    const doAppend = options?.append ?? false

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
                parent_id?: string
                left?: string
                right?: string
                dimension?: string
              }
              if (existingIds.has(node.id)) continue
              existingIds.add(node.id)
              nodeCount++

              const suggestion = {
                id: node.id,
                text: node.text,
                type: (node.type ?? 'bubble') as 'bubble' | 'branch' | 'label',
                source_llm: node.source_llm,
                mode: node.mode,
                parent_id: node.parent_id,
                left: node.left,
                right: node.right,
                dimension: node.dimension,
              }
              if (doAppend) {
                panelsStore.appendNodePaletteSuggestion(suggestion)
              } else {
                panelsStore.setNodePaletteSuggestions([
                  ...panelsStore.nodePalettePanel.suggestions,
                  suggestion,
                ])
              }
              // Yield to next frame so each node paints progressively (streaming UX)
              await new Promise<void>((r) => requestAnimationFrame(() => r()))
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
      if (useGlobalAbort) {
        abortController.value = null
      }
    }

    return nodeCount
  }

  async function startSessionsForAllParents(
    parents: Stage2Parent[],
    dt: DiagramType | null,
    dimension: string
  ): Promise<void> {
    if (!sessionId.value || !topicText.value) return
    isLoading.value = true
    errorMessage.value = null
    const sharedIds = new Set(panelsStore.nodePalettePanel.suggestions.map((s) => s.id))
    const basePayload: Record<string, unknown> = {
      diagram_type: dt,
      diagram_data: diagramData.value,
      language,
      stage: stage2StageNameForType(dt),
      mode: parents[0].name,
    }
    try {
      const results = await Promise.allSettled(
        parents.map((parent) => {
          const payload = {
            ...basePayload,
            session_id: `${sessionId.value}_${parent.id}`,
            stage_data: buildStageDataForParent(parent, dt, { dimension }),
            mode: parent.name,
          }
          return streamBatch(NODE_PALETTE_START, payload, {
            append: true,
            sharedExistingIds: sharedIds,
            useGlobalAbort: false,
          })
        })
      )
      const firstRejection = results.find((r) => r.status === 'rejected')
      if (
        firstRejection &&
        firstRejection.status === 'rejected' &&
        !isAbortError(firstRejection.reason)
      ) {
        errorMessage.value =
          firstRejection.reason instanceof Error
            ? firstRejection.reason.message
            : String(firstRejection.reason)
        onError?.(errorMessage.value)
      }
    } finally {
      isLoading.value = false
    }
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
    const canStartWithoutTopic = isDimensionsStage && diagramType.value === 'bridge_map'
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
    const resolvedStage = panelsStore.nodePalettePanel.stage ?? (isStaged ? stage : undefined)
    const stageData = panelsStore.nodePalettePanel.stage_data ?? undefined
    const displayMode =
      panelsStore.nodePalettePanel.mode ??
      (dt === 'double_bubble_map'
        ? 'similarities'
        : dt === 'multi_flow_map'
          ? 'causes'
          : resolvedStage)
    const requestMode =
      dt === 'double_bubble_map' ? 'both' : dt === 'multi_flow_map' ? 'both' : displayMode
    const paletteUpdates: {
      stage?: string
      stage_data?: Record<string, unknown> | null
      mode?: string
      selected?: string[]
    } = {}
    if (!keepSessionId) {
      paletteUpdates.selected = []
    }
    if (isStaged) {
      paletteUpdates.stage = resolvedStage
      paletteUpdates.stage_data = stageData ?? null
      paletteUpdates.mode = displayMode
    } else if (dt === 'double_bubble_map' || dt === 'multi_flow_map') {
      paletteUpdates.mode = displayMode
    }
    if (keepSessionId) {
      panelsStore.updateNodePalette(paletteUpdates)
    } else {
      const diagramKey = getNodePaletteDiagramKey(
        dt ?? 'unknown',
        savedDiagramsStore.activeDiagramId,
        route.query.diagramId as string | undefined
      )
      panelsStore.clearNodePaletteSession(diagramKey)
      if (dt === 'double_bubble_map' || dt === 'multi_flow_map') {
        panelsStore.setNodePaletteSuggestions([])
      } else if (isStaged) {
        panelsStore.setNodePaletteSuggestions([])
      } else {
        panelsStore.setNodePaletteSuggestions([])
      }
      panelsStore.updateNodePalette(paletteUpdates)
    }

    isLoading.value = true
    try {
      const stage2Names = ['children', 'substeps', 'subparts']
      const isStage2 = isStaged && resolvedStage && stage2Names.includes(resolvedStage)
      const parents = isStage2 && dt ? getStage2ParentsForDiagram(dt, nodes, connections) : []
      const dim =
        (stageData as { dimension?: string })?.dimension ??
        (diagramStore.data as { dimension?: string })?.dimension ??
        ''

      if (isStage2 && parents.length > 1) {
        await startSessionsForAllParents(parents, dt, dim)
        return true
      }

      const payload: Record<string, unknown> = {
        session_id: sessionId.value,
        diagram_type: dt,
        diagram_data: diagramData.value,
        language,
        mode: requestMode,
      }
      if (isStaged && resolvedStage) {
        payload.stage = resolvedStage
        if (stageData && Object.keys(stageData).length > 0) {
          payload.stage_data = stageData
        }
      }
      await streamBatch(NODE_PALETTE_START, payload)
      return true
    } catch (err) {
      if (isAbortError(err)) return false
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
    if (!sessionId.value || (!centerTopic.value && !canLoadWithoutTopic) || isLoadingMore.value)
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
      const nextBatchMode =
        panelsStore.nodePalettePanel.mode ??
        (dt === 'double_bubble_map' ? 'similarities' : dt === 'multi_flow_map' ? 'causes' : stage)
      const nextBatchRequestMode =
        dt === 'double_bubble_map' || dt === 'multi_flow_map' ? 'both' : nextBatchMode
      const payload: Record<string, unknown> = {
        session_id: sessionId.value,
        diagram_type: dt,
        center_topic: centerTopic.value || ' ',
        language,
        mode: nextBatchRequestMode,
      }
      if (isStaged && stage) {
        payload.stage = stage
        let mergedStageData = stageData ?? {}
        if (dt === 'bridge_map' && stage === 'dimensions') {
          const data = diagramData.value as { analogies?: Array<{ left: string; right: string }> }
          const analogies = data?.analogies
          if (analogies?.length && !mergedStageData.analogies) {
            mergedStageData = { ...mergedStageData, analogies }
          }
        }
        if (Object.keys(mergedStageData).length > 0) {
          payload.stage_data = mergedStageData
        }
      }
      await streamBatch(NODE_PALETTE_NEXT, payload)
      return true
    } catch (err) {
      if (isAbortError(err)) return false
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

    const mode =
      panelsStore.nodePalettePanel.mode ??
      (diagramType.value === 'double_bubble_map' ? 'similarities' : 'causes')

    const diagramKey = getNodePaletteDiagramKey(
      diagramType.value ?? 'unknown',
      savedDiagramsStore.activeDiagramId,
      route.query.diagramId as string | undefined
    )

    return applySelectionToDiagram({
      diagramStore: diagramStore as Parameters<typeof applySelectionToDiagram>[0]['diagramStore'],
      panelsStore: panelsStore as Parameters<typeof applySelectionToDiagram>[0]['panelsStore'],
      diagramType: diagramType.value,
      diagramKey,
      toApply,
      stage,
      stageData: panelsStore.nodePalettePanel.stage_data ?? undefined,
      mode,
      language,
      startSession,
      startSessionsForAllParents,
    })
  }

  function cancel(): void {
    if (abortController.value) {
      abortController.value.abort()
    }
    sessionId.value = null
    centerTopic.value = ''
    const diagramKey = getNodePaletteDiagramKey(
      diagramType.value ?? 'unknown',
      savedDiagramsStore.activeDiagramId,
      route.query.diagramId as string | undefined
    )
    panelsStore.clearNodePaletteSession(diagramKey)
    panelsStore.setNodePaletteSuggestions([])
    panelsStore.updateNodePalette({ selected: [] })
    panelsStore.closeNodePalette()
  }

  /** Close panel without clearing suggestions/selection - save to session store for reopen */
  function dismiss(): void {
    if (abortController.value) {
      abortController.value.abort()
    }
    sessionId.value = null
    const diagramKey = getNodePaletteDiagramKey(
      diagramType.value ?? 'unknown',
      savedDiagramsStore.activeDiagramId,
      route.query.diagramId as string | undefined
    )
    panelsStore.saveNodePaletteSession(diagramKey)
    panelsStore.closeNodePalette()
  }

  async function switchTab(
    mode: 'similarities' | 'differences' | 'causes' | 'effects'
  ): Promise<boolean> {
    const dt = diagramType.value
    const isDoubleBubble = dt === 'double_bubble_map'
    const isMultiFlow = dt === 'multi_flow_map'
    if (!isDoubleBubble && !isMultiFlow) return false
    if (isDoubleBubble && mode !== 'similarities' && mode !== 'differences') return false
    if (isMultiFlow && mode !== 'causes' && mode !== 'effects') return false
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    panelsStore.updateNodePalette({ mode })
    errorMessage.value = null
    const defaultMode = isDoubleBubble ? 'similarities' : 'causes'
    const suggestionsForMode = panelsStore.nodePalettePanel.suggestions.filter(
      (s) => (s.mode ?? defaultMode) === mode
    )
    if (suggestionsForMode.length > 0) {
      return true
    }
    return startSession({ keepSessionId: true })
  }

  const stage2Parents = computed(() => {
    const dt = diagramType.value
    const nodes = diagramStore.data?.nodes ?? []
    const connections = diagramStore.data?.connections
    return getStage2ParentsForDiagram(dt, nodes, connections)
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

  const stage2StageName = computed(() => stage2StageNameForType(diagramType.value))

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
      dt === 'mindmap'
        ? 'branch_id'
        : dt === 'flow_map'
          ? 'step_id'
          : dt === 'tree_map'
            ? 'category_id'
            : dt === 'brace_map'
              ? 'part_id'
              : undefined
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
    })
    errorMessage.value = null
    const parentNameNorm = (parentName ?? '').trim()
    const suggestionsForMode = panelsStore.nodePalettePanel.suggestions.filter(
      (s) => suggestionBelongsToParent(s, parentId, parentNameNorm)
    )
    if (suggestionsForMode.length > 0) {
      return true
    }
    return startSession({ keepSessionId: true })
  }

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
    if (_asSingleton) {
      _nodePaletteInstance = null
    }
  })

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

  const bridgeMapDimension = computed(() => {
    if (diagramType.value !== 'bridge_map') return ''
    const stage = panelsStore.nodePalettePanel.stage
    const mode = panelsStore.nodePalettePanel.mode as string
    if (stage !== 'pairs' && mode !== 'pairs') return ''
    const sd = panelsStore.nodePalettePanel.stage_data as { dimension?: string } | undefined
    return (sd?.dimension ?? '').trim()
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
    diagramType: rawDiagramType,
    diagramData,
    doubleBubbleTopics,
    bridgeMapDimension,
    isStagedDiagram,
    isDimensionsStage,
    showNextButton,
    stage2Parents,
    stage2StageName,
    defaultStage,
    getStageDataForParent,
    startSession,
    loadNextBatch,
    toggleSelection,
    finishSelection,
    cancel,
    dismiss,
    switchTab,
    switchStageTab,
  }
}
