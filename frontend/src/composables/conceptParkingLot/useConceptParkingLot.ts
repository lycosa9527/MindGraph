/**
 * Concept parking lot (概念停车场) — mind-map AI suggestions with drag-to-canvas.
 *
 * Ported from node palette waterfall mode but uses isolated store state and session keys
 * so the staged node palette flow is unaffected.
 */
import { computed, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { storeToRefs } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import { buildDiagramData } from '@/composables/nodePalette/diagramDataBuilder'
import {
  MINDMAP_WATERFALL_NODES_PER_LLM,
  NODE_PALETTE_START,
} from '@/composables/nodePalette/constants'
import { isAbortError } from '@/composables/nodePalette/errors'
import {
  resolveMindMapWaterfallSources,
  tabLabel,
} from '@/composables/nodePalette/mindMapWaterfallHelpers'
import { getConceptParkingLotDiagramKey } from '@/composables/nodePalette/sessionKeys'
import { streamNodePaletteBatch } from '@/composables/nodePalette/streamNodePaletteBatch'
import { useDiagramStore, usePanelsStore, useUIStore } from '@/stores'
import { isLearningSheetBlankDisplayText } from '@/stores/specLoader/utils'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { NodeSuggestion } from '@/types/panels'

export interface UseConceptParkingLotOptions {
  onError?: (error: string) => void
  _asSingleton?: boolean
}

let _conceptParkingLotInstance: ReturnType<typeof useConceptParkingLot> | null = null

export function getConceptParkingLot(options: UseConceptParkingLotOptions = {}) {
  if (!_conceptParkingLotInstance) {
    _conceptParkingLotInstance = useConceptParkingLot({ ...options, _asSingleton: true })
  }
  return _conceptParkingLotInstance
}

export function useConceptParkingLot(options: UseConceptParkingLotOptions = {}) {
  const { onError, _asSingleton } = options
  const { t } = useI18n()
  const route = useRoute()
  const diagramStore = useDiagramStore()
  const panelsStore = usePanelsStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const uiStore = useUIStore()
  const { promptLanguage } = storeToRefs(uiStore)

  const sessionId = ref<string | null>(null)
  const isLoading = ref(false)
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
    paletteStreamPhase.value = 'idle'
    errorMessage.value = null
  }

  function abortAllPaletteStreaming(): void {
    endPaletteStreamSession()
    abortInFlightPaletteFetchesOnly()
  }

  const suggestionSink = {
    getSuggestions: () => panelsStore.conceptParkingLotPanel.suggestions,
    clearSuggestions: () => panelsStore.setConceptParkingLotSuggestions([]),
    appendSuggestion: (suggestion: NodeSuggestion) =>
      panelsStore.appendConceptParkingLotSuggestion(suggestion),
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
    const all = panelsStore.conceptParkingLotPanel.suggestions
    const mode = panelsStore.conceptParkingLotPanel.mode
    if (!mode) return all
    return all.filter((s) => (s.parent_id ?? s.mode ?? '') === mode)
  })

  const selectedIds = computed(() => panelsStore.conceptParkingLotPanel.selected)

  const sourceTabs = computed(() => panelsStore.conceptParkingLotPanel.sourceTabs ?? [])

  function generateSessionId(): string {
    return `cpl_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
  }

  function diagramKey(): string {
    return getConceptParkingLotDiagramKey(
      savedDiagramsStore.activeDiagramId,
      route.query.diagramId as string | undefined
    )
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

    const nodes = diagramStore.data.nodes
    const sources = resolveMindMapWaterfallSources(diagramStore.selectedNodes, nodes)
    const tabs = sources.map((s) => ({ id: s.id, name: tabLabel(s.name) }))

    const keepSessionId = sessionOptions?.keepSessionId ?? false
    const key = diagramKey()
    if (!keepSessionId || !sessionId.value) {
      sessionId.value = generateSessionId()
      panelsStore.clearConceptParkingLotSession(key)
      panelsStore.setConceptParkingLotSuggestions([])
    }

    errorMessage.value = null
    panelsStore.updateConceptParkingLot({
      sourceTabs: tabs,
      mode: tabs[0]?.id ?? 'topic',
      selected: keepSessionId ? panelsStore.conceptParkingLotPanel.selected : [],
    })

    isLoading.value = true
    try {
      ensurePaletteStreamSession()
      const sharedIds = new Set(panelsStore.conceptParkingLotPanel.suggestions.map((s) => s.id))
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

  function switchTab(tabId: string): void {
    if (panelsStore.conceptParkingLotPanel.mode === tabId) return
    panelsStore.updateConceptParkingLot({ mode: tabId })
  }

  function toggleSelection(nodeId: string): void {
    panelsStore.toggleConceptParkingLotSelection(nodeId)
  }

  function dismiss(): void {
    abortAllPaletteStreaming()
    panelsStore.closeConceptParkingLot()
    sessionId.value = null
    panelsStore.saveConceptParkingLotSession(diagramKey())
  }

  function removeDroppedSuggestions(suggestionIds: string[]): void {
    panelsStore.removeConceptParkingLotSuggestions(suggestionIds)
  }

  function resetSessionState(): void {
    abortAllPaletteStreaming()
    sessionId.value = null
    errorMessage.value = null
  }

  eventBus.onWithOwner('diagram:loaded', resetSessionState, 'useConceptParkingLot')
  eventBus.onWithOwner('diagram:type_changed', resetSessionState, 'useConceptParkingLot')
  eventBus.onWithOwner(
    'concept_parking_lot:streaming_stop_requested',
    abortAllPaletteStreaming,
    'useConceptParkingLot'
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner('useConceptParkingLot')
    abortAllPaletteStreaming()
    if (_asSingleton) {
      _conceptParkingLotInstance = null
    }
  })

  return {
    isLoading,
    paletteStreamPhase,
    errorMessage,
    suggestions,
    selectedIds,
    sourceTabs,
    toggleSelection,
    dismiss,
    switchTab,
    refreshSession,
    startSession,
    removeDroppedSuggestions,
  }
}
