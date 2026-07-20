/**
 * AI Brainstorm (AI头脑风暴) — mind-map side tool for new Canvas.
 *
 * Isolated from Node Palette (own store/session/events). Reuses shared SSE helpers
 * and stage utilities from the nodePalette package without modifying that module.
 */
import { computed, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { storeToRefs } from 'pinia'

import { applyAiBrainstormSelection } from '@/composables/aiBrainstorm/applyAiBrainstormSelection'
import { eventBus } from '@/composables/core/useEventBus'
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import { buildDiagramData } from '@/composables/nodePalette/diagramDataBuilder'
import {
  MINDMAP_WATERFALL_NODES_PER_LLM,
  NODE_PALETTE_NEXT,
  NODE_PALETTE_START,
  getParentIdFromStageData,
} from '@/composables/nodePalette/constants'
import { isAbortError } from '@/composables/nodePalette/errors'
import {
  resolveMindMapWaterfallSources,
  tabLabel,
} from '@/composables/nodePalette/mindMapWaterfallHelpers'
import { getAiBrainstormDiagramKey } from '@/composables/nodePalette/sessionKeys'
import {
  buildStageDataForParent,
  getDefaultStage,
  getStage2ParentsForDiagram,
  type Stage2Parent,
  stage2StageNameForType,
} from '@/composables/nodePalette/stageHelpers'
import { streamNodePaletteBatch } from '@/composables/nodePalette/streamNodePaletteBatch'
import { useDiagramStore, useLLMResultsStore, usePanelsStore, useUIStore } from '@/stores'
import { isLearningSheetBlankDisplayText } from '@/stores/specLoader/utils'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { resolveDiagramLlmModel } from '@/utils/resolveDiagramLlmModel'
import type { NodeSuggestion } from '@/types/panels'

export interface UseAiBrainstormOptions {
  onError?: (error: string) => void
  _asSingleton?: boolean
}

let _aiBrainstormInstance: ReturnType<typeof useAiBrainstorm> | null = null

export function getAiBrainstorm(options: UseAiBrainstormOptions = {}) {
  if (!_aiBrainstormInstance) {
    _aiBrainstormInstance = useAiBrainstorm({ ...options, _asSingleton: true })
  }
  return _aiBrainstormInstance
}

export function useAiBrainstorm(options: UseAiBrainstormOptions = {}) {
  const { onError, _asSingleton } = options
  const { t } = useI18n()
  const route = useRoute()
  const diagramStore = useDiagramStore()
  const panelsStore = usePanelsStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()
  const uiStore = useUIStore()
  const { promptLanguage } = storeToRefs(uiStore)

  const sessionId = ref<string | null>(null)
  const isLoading = ref(false)
  const isLoadingMore = ref(false)
  const errorMessage = ref<string | null>(null)
  const abortController = ref<AbortController | null>(null)
  const paletteActiveControllers = ref<AbortController[]>([])
  const paletteStreamSession = ref<AbortController | null>(null)
  const paletteStreamPhase = ref<'idle' | 'requesting' | 'streaming'>('idle')
  const streamBatchDepth = { value: 0 }
  const firstNodeReceivedInBatch = { value: false }

  function ensurePaletteStreamSession(): void {
    if (!paletteStreamSession.value || paletteStreamSession.value.signal.aborted) {
      paletteStreamSession.value = new AbortController()
    }
  }

  function endPaletteStreamSession(): void {
    if (paletteStreamSession.value) {
      try {
        paletteStreamSession.value.abort()
      } catch {
        // ignore
      }
    }
  }

  function abortInFlightPaletteFetchesOnly(): void {
    const seen = new Set<AbortController>()
    for (const c of paletteActiveControllers.value) {
      seen.add(c)
    }
    if (abortController.value) {
      seen.add(abortController.value)
    }
    paletteActiveControllers.value = []
    abortController.value = null
    for (const c of seen) {
      try {
        c.abort()
      } catch {
        // ignore
      }
    }
    isLoading.value = false
    isLoadingMore.value = false
    paletteStreamPhase.value = 'idle'
    errorMessage.value = null
  }

  function abortAllPaletteStreaming(): void {
    endPaletteStreamSession()
    abortInFlightPaletteFetchesOnly()
  }

  const suggestionSink = {
    getSuggestions: () => panelsStore.aiBrainstormPanel.suggestions,
    clearSuggestions: () => panelsStore.setAiBrainstormSuggestions([]),
    appendSuggestion: (suggestion: NodeSuggestion) =>
      panelsStore.appendAiBrainstormSuggestion(suggestion),
  }

  const streamDeps = {
    panelsStore,
    promptLanguage,
    abortController,
    paletteActiveControllers,
    paletteStreamSession,
    errorMessage,
    onError,
    paletteStreamPhase,
    streamBatchDepth,
    firstNodeReceivedInBatch,
    suggestionSink,
  }

  function streamBatch(
    url: string,
    payload: Record<string, unknown>,
    batchOptions?: {
      append?: boolean
      sharedExistingIds?: Set<string>
      useGlobalAbort?: boolean
    }
  ): Promise<number> {
    return streamNodePaletteBatch(streamDeps, url, payload, batchOptions)
  }

  const diagramData = computed(() => {
    const nodes = diagramStore.data?.nodes ?? []
    return buildDiagramData('mindmap', nodes)
  })

  const topicText = computed(() => {
    const data = diagramData.value as Record<string, unknown>
    const topic = (data.topic as string) ?? ''
    const center = data.center as { text?: string } | undefined
    return (topic || center?.text || '').trim()
  })

  const suggestions = computed(() => {
    const all = panelsStore.aiBrainstormPanel.suggestions
    const mode = panelsStore.aiBrainstormPanel.mode
    const stage = panelsStore.aiBrainstormPanel.stage
    const stageData = panelsStore.aiBrainstormPanel.stage_data
    if (!mode) return all
    const parentId = getParentIdFromStageData(
      'mindmap',
      stage ?? undefined,
      (stageData ?? undefined) as Record<string, unknown>
    )
    return all.filter((s) => {
      if (parentId && s.parent_id) return s.parent_id === parentId
      return (s.parent_id ?? s.mode ?? '') === mode
    })
  })

  const selectedIds = computed(() => panelsStore.aiBrainstormPanel.selected)
  const sourceTabs = computed(() => panelsStore.aiBrainstormPanel.sourceTabs ?? [])
  const currentStage = computed(() => panelsStore.aiBrainstormPanel.stage ?? '')
  const showNextButton = computed(() => currentStage.value === 'branches')
  const stage2Parents = computed(() =>
    getStage2ParentsForDiagram('mindmap', diagramStore.data?.nodes ?? [], diagramStore.data?.connections)
  )
  const showStage2Tabs = computed(
    () => stage2Parents.value.length > 0 && currentStage.value === 'children'
  )

  function generateSessionId(): string {
    return `aib_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
  }

  function diagramKey(): string {
    return getAiBrainstormDiagramKey(
      savedDiagramsStore.activeDiagramId,
      route.query.diagramId as string | undefined
    )
  }

  async function startSessionsForAllParents(parents: Stage2Parent[]): Promise<void> {
    if (!sessionId.value || !topicText.value) return
    isLoading.value = true
    errorMessage.value = null
    const sharedIds = new Set(panelsStore.aiBrainstormPanel.suggestions.map((s) => s.id))
    const basePayload: Record<string, unknown> = {
      diagram_type: 'mindmap',
      diagram_data: diagramData.value,
      language: promptLanguage.value,
      stage: stage2StageNameForType('mindmap'),
      nodes_per_llm: MINDMAP_WATERFALL_NODES_PER_LLM,
      llm_models: [resolveDiagramLlmModel(llmResultsStore.selectedModel)],
      mode: parents[0]?.name,
    }
    try {
      ensurePaletteStreamSession()
      const results = await Promise.allSettled(
        parents.map((parent) => {
          const payload = {
            ...basePayload,
            session_id: `${sessionId.value}_${parent.id}`,
            stage_data: buildStageDataForParent(parent, 'mindmap'),
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

  async function startFromCanvasSelection(keepSessionId: boolean): Promise<boolean> {
    const nodes = diagramStore.data?.nodes ?? []
    const sources = resolveMindMapWaterfallSources(diagramStore.selectedNodes, nodes)
    const tabs = sources.map((s) => ({ id: s.id, name: tabLabel(s.name) }))
    const key = diagramKey()
    if (!keepSessionId || !sessionId.value) {
      sessionId.value = generateSessionId()
      panelsStore.clearAiBrainstormSession(key)
      panelsStore.setAiBrainstormSuggestions([])
    }
    errorMessage.value = null
    panelsStore.updateAiBrainstorm({
      sourceTabs: tabs,
      mode: tabs[0]?.id ?? 'topic',
      stage: sources[0]?.stage ?? 'branches',
      stage_data: sources[0]?.stageData ?? null,
      selected: keepSessionId ? panelsStore.aiBrainstormPanel.selected : [],
    })
    isLoading.value = true
    try {
      ensurePaletteStreamSession()
      const sharedIds = new Set(panelsStore.aiBrainstormPanel.suggestions.map((s) => s.id))
      const results = await Promise.allSettled(
        sources.map((source) => {
          const stageData = {
            ...(source.stageData ?? {}),
            source_node_id: source.id,
          }
          const payload: Record<string, unknown> = {
            session_id: `${sessionId.value}_${source.id}`,
            diagram_type: 'mindmap',
            diagram_data: diagramData.value,
            language: promptLanguage.value,
            nodes_per_llm: MINDMAP_WATERFALL_NODES_PER_LLM,
            llm_models: [resolveDiagramLlmModel(llmResultsStore.selectedModel)],
            stage: source.stage,
            stage_data: stageData,
            mode: source.id,
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
      return true
    } finally {
      isLoading.value = false
    }
  }

  async function startSession(sessionOptions?: { keepSessionId?: boolean }): Promise<boolean> {
    const dt = diagramStore.type
    if ((dt !== 'mindmap' && dt !== 'mind_map') || !diagramStore.data?.nodes?.length) {
      errorMessage.value = t('nodePalette.error.createDiagramFirst')
      return false
    }

    const topic = topicText.value.trim()
    if (!topic || isPlaceholderText(topic) || isLearningSheetBlankDisplayText(topic)) {
      errorMessage.value = t('nodePalette.error.replacePlaceholder')
      return false
    }

    const keepSessionId = sessionOptions?.keepSessionId ?? false
    const selected = diagramStore.selectedNodes
    if (selected.length > 0) {
      return startFromCanvasSelection(keepSessionId)
    }

    const nodes = diagramStore.data.nodes
    const connections = diagramStore.data?.connections
    const resolvedStage =
      panelsStore.aiBrainstormPanel.stage ?? getDefaultStage('mindmap', nodes, connections)
    const stageData = panelsStore.aiBrainstormPanel.stage_data ?? undefined
    const isStage2 = resolvedStage === 'children'
    const parents = isStage2 ? getStage2ParentsForDiagram('mindmap', nodes, connections) : []

    const key = diagramKey()
    if (!keepSessionId || !sessionId.value) {
      sessionId.value = generateSessionId()
      panelsStore.clearAiBrainstormSession(key)
      panelsStore.setAiBrainstormSuggestions([])
    }

    errorMessage.value = null
    if (isStage2 && parents.length > 0) {
      const tabs = parents.map((p) => ({ id: p.id, name: p.name }))
      const activeParent =
        parents.find((p) => p.name === panelsStore.aiBrainstormPanel.mode) ?? parents[0]
      panelsStore.updateAiBrainstorm({
        stage: 'children',
        stage_data: buildStageDataForParent(activeParent, 'mindmap'),
        mode: activeParent.name,
        sourceTabs: tabs,
        selected: keepSessionId ? panelsStore.aiBrainstormPanel.selected : [],
      })
      if (parents.length > 1 && !keepSessionId) {
        await startSessionsForAllParents(parents)
        return true
      }
    } else {
      panelsStore.updateAiBrainstorm({
        stage: 'branches',
        stage_data: null,
        mode: 'branches',
        sourceTabs: [{ id: 'topic', name: tabLabel(topic) }],
        selected: keepSessionId ? panelsStore.aiBrainstormPanel.selected : [],
      })
    }

    isLoading.value = true
    try {
      ensurePaletteStreamSession()
      const payload: Record<string, unknown> = {
        session_id: sessionId.value,
        diagram_type: 'mindmap',
        diagram_data: diagramData.value,
        language: promptLanguage.value,
        nodes_per_llm: MINDMAP_WATERFALL_NODES_PER_LLM,
        llm_models: [resolveDiagramLlmModel(llmResultsStore.selectedModel)],
        stage: panelsStore.aiBrainstormPanel.stage,
        mode: panelsStore.aiBrainstormPanel.mode,
      }
      const sd = panelsStore.aiBrainstormPanel.stage_data
      if (sd && Object.keys(sd).length > 0) {
        payload.stage_data = sd
      }
      await streamBatch(NODE_PALETTE_START, payload, { append: keepSessionId })
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

  async function refreshSession(): Promise<boolean> {
    return startSession({ keepSessionId: false })
  }

  async function loadNextBatch(): Promise<boolean> {
    if (!sessionId.value || isLoadingMore.value) return false
    isLoadingMore.value = true
    try {
      ensurePaletteStreamSession()
      const stage = panelsStore.aiBrainstormPanel.stage ?? undefined
      const stageData = panelsStore.aiBrainstormPanel.stage_data ?? undefined
      const mode = panelsStore.aiBrainstormPanel.mode ?? stage
      const payload: Record<string, unknown> = {
        session_id: sessionId.value,
        diagram_type: 'mindmap',
        center_topic: topicText.value || ' ',
        language: promptLanguage.value,
        mode,
        nodes_per_llm: MINDMAP_WATERFALL_NODES_PER_LLM,
        llm_models: [resolveDiagramLlmModel(llmResultsStore.selectedModel)],
      }
      if (stage) payload.stage = stage
      if (stageData && Object.keys(stageData).length > 0) payload.stage_data = stageData
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

  function switchTab(tabId: string): void {
    if (panelsStore.aiBrainstormPanel.mode === tabId) return
    const parent = stage2Parents.value.find((p) => p.id === tabId || p.name === tabId)
    if (parent && currentStage.value === 'children') {
      void switchStageTab(parent.id, parent.name)
      return
    }
    panelsStore.updateAiBrainstorm({ mode: tabId })
  }

  async function switchStageTab(parentId: string, parentName: string): Promise<boolean> {
    if (panelsStore.aiBrainstormPanel.mode === parentName) return true
    const stageData = buildStageDataForParent({ id: parentId, name: parentName }, 'mindmap')
    const cached = panelsStore.aiBrainstormPanel.suggestions.filter(
      (s) => s.parent_id === parentId || (s.mode ?? '') === parentName
    )
    panelsStore.updateAiBrainstorm({
      stage: 'children',
      stage_data: stageData,
      mode: parentName,
    })
    errorMessage.value = null
    if (isLoading.value || cached.length > 0) return true
    abortInFlightPaletteFetchesOnly()
    return startSession({ keepSessionId: true })
  }

  function toggleSelection(nodeId: string): void {
    panelsStore.toggleAiBrainstormSelection(nodeId)
  }

  async function finishSelection(): Promise<boolean> {
    const selected = panelsStore.aiBrainstormPanel.selected
    const suggestionsList = panelsStore.aiBrainstormPanel.suggestions
    const toApply = suggestionsList.filter((s) => selected.includes(s.id))
    if (toApply.length === 0) return false

    diagramStore.pushHistory(t('nodePalette.history.replaceAddNodes'))
    return applyAiBrainstormSelection({
      diagramStore,
      diagramKey: diagramKey(),
      toApply,
      stage: panelsStore.aiBrainstormPanel.stage ?? undefined,
      stageData: panelsStore.aiBrainstormPanel.stage_data ?? undefined,
      mode: panelsStore.aiBrainstormPanel.mode ?? 'branches',
      updatePanel: (updates) => panelsStore.updateAiBrainstorm(updates),
      clearSuggestions: () => panelsStore.setAiBrainstormSuggestions([]),
      clearSession: (key) => panelsStore.clearAiBrainstormSession(key),
      closePanel: () => panelsStore.closeAiBrainstorm(),
      startSession,
      startSessionsForAllParents,
    })
  }

  function cancel(): void {
    abortAllPaletteStreaming()
    const key = diagramKey()
    panelsStore.closeAiBrainstorm()
    sessionId.value = null
    panelsStore.clearAiBrainstormSession(key)
    panelsStore.setAiBrainstormSuggestions([])
    panelsStore.updateAiBrainstorm({ selected: [] })
  }

  function dismiss(): void {
    abortAllPaletteStreaming()
    panelsStore.closeAiBrainstorm()
    sessionId.value = null
    panelsStore.saveAiBrainstormSession(diagramKey())
  }

  function removeDroppedSuggestions(suggestionIds: string[]): void {
    panelsStore.removeAiBrainstormSuggestions(suggestionIds)
  }

  function resetSessionState(): void {
    abortAllPaletteStreaming()
    sessionId.value = null
    errorMessage.value = null
  }

  eventBus.onWithOwner('diagram:loaded', resetSessionState, 'useAiBrainstorm')
  eventBus.onWithOwner('diagram:type_changed', resetSessionState, 'useAiBrainstorm')
  eventBus.onWithOwner(
    'ai_brainstorm:streaming_stop_requested',
    abortAllPaletteStreaming,
    'useAiBrainstorm'
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner('useAiBrainstorm')
    abortAllPaletteStreaming()
    if (_asSingleton) {
      _aiBrainstormInstance = null
    }
  })

  return {
    isLoading,
    isLoadingMore,
    paletteStreamPhase,
    errorMessage,
    suggestions,
    selectedIds,
    sourceTabs,
    currentStage,
    showNextButton,
    showStage2Tabs,
    stage2Parents,
    sessionId,
    toggleSelection,
    dismiss,
    cancel,
    switchTab,
    switchStageTab,
    refreshSession,
    startSession,
    loadNextBatch,
    finishSelection,
    removeDroppedSuggestions,
  }
}
