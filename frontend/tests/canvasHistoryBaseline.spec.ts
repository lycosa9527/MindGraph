import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { applyCanvasHistoryNavigationSync } from '@/composables/canvasPage/applyCanvasHistoryNavigationSync'
import { tryCollabGuardedUndo } from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import { useDiagramStore } from '@/stores/diagram'
import { useInlineRecommendationsStore } from '@/stores/inlineRecommendations'
import { useLLMResultsStore } from '@/stores/llmResults'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'

describe('canvas undo/redo baseline', () => {
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

  it('seeds baseline so the first edit is undoable', () => {
    setActivePinia(createPinia())
    const diagramStore = useDiagramStore()

    diagramStore.loadDefaultTemplate('mindmap')
    diagramStore.seedHistoryBaselineIfEmpty()

    expect(diagramStore.canUndo).toBe(false)

    const topic = diagramStore.data?.nodes.find((node) => node.id === 'topic')
    if (topic) {
      topic.text = 'Edited topic'
    }
    diagramStore.pushHistory('Edit topic')

    expect(diagramStore.canUndo).toBe(true)

    tryCollabGuardedUndo()

    const restoredTopic = diagramStore.data?.nodes.find((node) => node.id === 'topic')
    expect(restoredTopic?.text).not.toBe('Edited topic')
    expect(diagramStore.selectedNodes).toEqual([])
  })

  it('aborts in-flight LLM work before undo restores a snapshot', () => {
    setActivePinia(createPinia())
    const llmStore = useLLMResultsStore()
    let aborted = false
    const controller = new AbortController()
    controller.signal.addEventListener('abort', () => {
      aborted = true
    })
    llmStore.addAbortController(controller)
    llmStore.startGeneration('sess-undo', 'mindmap')

    const inlineRecStore = useInlineRecommendationsStore()
    inlineRecStore.setStreamPhase('streaming')
    useMindMapSubgraphPreviewStore().beginGeneration('branch-1')

    applyCanvasHistoryNavigationSync()

    expect(aborted).toBe(true)
    expect(llmStore.isGenerating).toBe(false)
    expect(inlineRecStore.streamPhase).toBe('idle')
    expect(useMindMapSubgraphPreviewStore().isGenerating).toBe(false)
  })
})
