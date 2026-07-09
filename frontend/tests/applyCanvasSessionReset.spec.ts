import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { applyCanvasSessionReset } from '@/composables/canvasPage/applyCanvasSessionReset'
import { eventBus } from '@/composables/core/useEventBus'
import { useConceptMapFocusReviewStore } from '@/stores/conceptMapFocusReview'
import { useDiagramStore } from '@/stores/diagram'
import { useInlineRecommendationsStore } from '@/stores/inlineRecommendations'
import { useLLMResultsStore } from '@/stores/llmResults'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'
import { usePanelsStore } from '@/stores/panels'

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

    const resetRequested = vi.fn()
    eventBus.on('diagram:reset_requested', resetRequested)

    applyCanvasSessionReset()

    expect(aborted).toBe(true)
    expect(llmStore.isGenerating).toBe(false)
    expect(inlineRecStore.streamPhase).toBe('idle')
    expect(previewStore.isGenerating).toBe(false)
    expect(previewStore.generatingNodeId).toBeNull()
    expect(diagramStore.selectedNodes).toEqual([])
    expect(diagramStore.canPaste).toBe(false)
    expect(usePanelsStore().mindmatePanel.isOpen).toBe(false)
    expect(useConceptMapFocusReviewStore().streamPhase).toBe('idle')
    expect(resetRequested).toHaveBeenCalledTimes(1)

    eventBus.off('diagram:reset_requested', resetRequested)
  })
})
