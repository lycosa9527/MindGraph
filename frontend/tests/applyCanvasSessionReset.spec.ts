import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { applyCanvasSessionReset } from '@/composables/canvasPage/applyCanvasSessionReset'
import { canvasVirtualKeyboardOpen } from '@/composables/canvasToolbar/useCanvasVirtualKeyboardOpen'
import { resetMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { eventBus } from '@/composables/core/useEventBus'
import { useCanvasNodeIndicatorsStore } from '@/stores/canvasNodeIndicators'
import { useConceptMapFocusReviewStore } from '@/stores/conceptMapFocusReview'
import { useConceptMapRelationshipStore } from '@/stores/conceptMapRelationship'
import { useDiagramStore } from '@/stores/diagram'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'
import { useInlineRecommendationsStore } from '@/stores/inlineRecommendations'
import { useKittySessionStore } from '@/stores/kittySession'
import { useLLMResultsStore } from '@/stores/llmResults'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'
import { useOneSentenceStore } from '@/stores/oneSentence'
import { usePanelsStore } from '@/stores/panels'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

describe('applyCanvasSessionReset', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      matches: false,
      media: '',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })))
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }))
    resetMindMapSideToolbarState()
    canvasVirtualKeyboardOpen.value = false
  })

  it('aborts LLM requests, clears ancillary stores, and emits diagram:reset_requested', () => {
    setActivePinia(createPinia())

    const llmStore = useLLMResultsStore()
    let aborted = false
    const controller = new AbortController()
    controller.signal.addEventListener('abort', () => {
      aborted = true
    })
    llmStore.addAbortController(controller)
    llmStore.startGeneration('sess-1', 'mindmap')

    const inlineRecStore = useInlineRecommendationsStore()
    inlineRecStore.setStreamPhase('streaming')

    const previewStore = useMindMapSubgraphPreviewStore()
    previewStore.beginGeneration('branch-1')

    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')
    diagramStore.selectNodes(['topic'])
    if (diagramStore.data?.nodes?.length) {
      diagramStore.copySelectedNodes()
    }

    const relationshipStore = useConceptMapRelationshipStore()
    relationshipStore.setOptions('edge-1', ['causes', 'supports'])

    const translateStore = useDiagramTranslateUiStore()
    translateStore.openBanner()
    translateStore.beginStream()

    const kittySession = useKittySessionStore()
    kittySession.setWriteLockHolder('llm')
    kittySession.setHubScopeRevision(3)
    kittySession.setAsrListening(true)

    const indicators = useCanvasNodeIndicatorsStore()
    indicators.setTabRecActive('topic')
    indicators.setCollabSelected(['topic'])

    const oneSentence = useOneSentenceStore()
    const ephemeralBefore = oneSentence.ephemeralScope
    oneSentence.setLibraryScope('diagram-a')
    oneSentence.registerUserRequest('旧对话', 'done')

    const savedDiagrams = useSavedDiagramsStore()
    savedDiagrams.setActiveDiagram('diagram-a')

    canvasVirtualKeyboardOpen.value = true

    const resetRequested = vi.fn()
    eventBus.on('diagram:reset_requested', resetRequested)

    applyCanvasSessionReset()

    expect(resetRequested).toHaveBeenCalledWith({ diagramId: 'diagram-a' })
    expect(aborted).toBe(true)
    expect(llmStore.isGenerating).toBe(false)
    expect(inlineRecStore.streamPhase).toBe('idle')
    expect(previewStore.isGenerating).toBe(false)
    expect(previewStore.generatingNodeId).toBeNull()
    expect(diagramStore.selectedNodes).toEqual([])
    expect(diagramStore.canPaste).toBe(false)
    expect(usePanelsStore().mindmatePanel.isOpen).toBe(false)
    expect(useConceptMapFocusReviewStore().streamPhase).toBe('idle')
    expect(Object.keys(relationshipStore.allLabels)).toHaveLength(0)
    expect(translateStore.bannerVisible).toBe(false)
    expect(kittySession.writeLockHolder).toBeNull()
    expect(kittySession.hubScopeRevision).toBeNull()
    expect(kittySession.asrListening).toBe(false)
    expect(indicators.tabRecActive).toBeNull()
    expect(indicators.collabSelected.size).toBe(0)
    expect(oneSentence.messages).toHaveLength(0)
    expect(oneSentence.libraryScope).toBeNull()
    expect(oneSentence.ephemeralScope).not.toBe(ephemeralBefore)
    expect(savedDiagrams.activeDiagramId).toBeNull()
    expect(canvasVirtualKeyboardOpen.value).toBe(false)
    expect(resetRequested).toHaveBeenCalledTimes(1)

    eventBus.off('diagram:reset_requested', resetRequested)
  })
})
