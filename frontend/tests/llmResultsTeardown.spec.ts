import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  shouldSkipLibraryReloadDuringGeneration,
  shouldSkipLibraryReloadForActiveDiagram,
} from '@/composables/canvasPage/skipLibraryReloadDuringGeneration'
import {
  isLlmResultForCurrentSession,
  shouldPaintCompletedLlmModel,
  shouldStampCanvasOntoLlmResult,
  useLLMResultsStore,
} from '@/stores/llmResults'

describe('shouldSkipLibraryReloadForActiveDiagram', () => {
  it('skips when route id matches the already-active diagram (first autosave URL sync)', () => {
    expect(shouldSkipLibraryReloadForActiveDiagram('diag-1', 'diag-1')).toBe(true)
    // Generating flag must not be required — Enter edits also hit this path.
    expect(shouldSkipLibraryReloadDuringGeneration(false, 'diag-1', 'diag-1')).toBe(true)
    expect(shouldSkipLibraryReloadDuringGeneration(true, 'diag-1', 'diag-1')).toBe(true)
  })

  it('does not skip when switching to another diagram', () => {
    expect(shouldSkipLibraryReloadForActiveDiagram('diag-2', 'diag-1')).toBe(false)
    expect(shouldSkipLibraryReloadDuringGeneration(true, 'diag-2', 'diag-1')).toBe(false)
  })

  it('does not skip when active diagram is unset', () => {
    expect(shouldSkipLibraryReloadForActiveDiagram('diag-1', null)).toBe(false)
    expect(shouldSkipLibraryReloadDuringGeneration(true, 'diag-1', null)).toBe(false)
  })
})

describe('llmResults teardown', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
  })

  it('clearCache aborts registered in-flight controllers', () => {
    const store = useLLMResultsStore()

    let aborted = false
    const controller = new AbortController()
    controller.signal.addEventListener('abort', () => {
      aborted = true
    })
    store.addAbortController(controller)

    store.clearCache()

    expect(aborted).toBe(true)
    expect(store.isGenerating).toBe(false)
    expect(store.modelPhases.qwen).toBe('idle')
  })

  it('clearCachedResultsOnly clears results without aborting streams', () => {
    const store = useLLMResultsStore()

    store.startGeneration('session-1', 'mindmap', ['qwen', 'doubao'])
    store.storeResult('qwen', { success: true, spec: { topic: 't' }, elapsed: 1 })

    let aborted = false
    const controller = new AbortController()
    controller.signal.addEventListener('abort', () => {
      aborted = true
    })
    store.addAbortController(controller)

    store.clearCachedResultsOnly()

    expect(aborted).toBe(false)
    expect(store.isGenerating).toBe(true)
    expect(store.hasAnyResults).toBe(false)
    expect(store.selectedModel).toBeNull()
  })
})

describe('llmResults regenerate paint / stamp', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        onchange: null,
        addListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
  })

  it('paints the first success of the round even if selectedModel was reclaimed', () => {
    expect(
      shouldPaintCompletedLlmModel({
        paintedModel: null,
        selectedModel: 'deepseek',
        completedModel: 'deepseek',
      })
    ).toBe(true)
    expect(
      shouldPaintCompletedLlmModel({
        paintedModel: null,
        selectedModel: 'qwen',
        completedModel: 'deepseek',
      })
    ).toBe(true)
    expect(
      shouldPaintCompletedLlmModel({
        paintedModel: 'deepseek',
        selectedModel: 'deepseek',
        completedModel: 'qwen',
      })
    ).toBe(false)
    expect(
      shouldPaintCompletedLlmModel({
        paintedModel: 'deepseek',
        selectedModel: 'deepseek',
        completedModel: 'deepseek',
      })
    ).toBe(true)
  })

  it('drops completions from a superseded generate session', () => {
    expect(isLlmResultForCurrentSession('gen_2', 'gen_1')).toBe(false)
    expect(isLlmResultForCurrentSession('gen_2', 'gen_2')).toBe(true)
    expect(isLlmResultForCurrentSession(null, 'gen_2')).toBe(false)
  })

  it('refuses any canvas stamp while generating', () => {
    expect(
      shouldStampCanvasOntoLlmResult({
        isGenerating: true,
        selectedModel: 'deepseek',
      })
    ).toBe(false)
    expect(
      shouldStampCanvasOntoLlmResult({
        isGenerating: false,
        selectedModel: 'deepseek',
      })
    ).toBe(true)
  })

  it('drops store writes from a superseded generate session', async () => {
    setActivePinia(createPinia())
    const store = useLLMResultsStore()
    store.startGeneration('gen_2', 'mindmap', ['qwen', 'deepseek'])

    const painted = await store.handleModelSuccess(
      'deepseek',
      { topic: 'stale' },
      'mindmap',
      1,
      'gen_1'
    )
    store.handleModelError('qwen', 'timeout', 1, undefined, 'gen_1')

    expect(painted).toBe(false)
    expect(store.results.deepseek).toBeUndefined()
    expect(store.results.qwen).toBeUndefined()
  })

  it('persists 2+ results even when selectedModel was never painted', () => {
    setActivePinia(createPinia())
    const store = useLLMResultsStore()
    store.storeResult('qwen', { success: true, spec: { topic: 'q' }, elapsed: 1 })
    store.storeResult('deepseek', { success: true, spec: { topic: 'd' }, elapsed: 1 })

    const persisted = store.getResultsForPersistence()
    expect(persisted?.selectedModel).toBe('qwen')
    expect(Object.keys(persisted?.results ?? {}).sort()).toEqual(['deepseek', 'qwen'])
  })

  it('clones persisted results so a later store write cannot mutate a queued save', () => {
    setActivePinia(createPinia())
    const store = useLLMResultsStore()
    store.setSelectedModel('qwen')
    store.storeResult('qwen', { success: true, spec: { topic: 'q' }, elapsed: 1 })
    store.storeResult('deepseek', { success: true, spec: { topic: 'd' }, elapsed: 1 })

    const persisted = store.getResultsForPersistence()
    store.storeResult('qwen', { success: true, spec: { topic: 'mutated' }, elapsed: 2 })
    expect(persisted?.results.qwen.spec).toEqual({ topic: 'q' })
  })

  it('does not restore saved llm_results over an in-flight generate', () => {
    setActivePinia(createPinia())
    const store = useLLMResultsStore()
    store.startGeneration('gen_live', 'mindmap', ['qwen'])
    store.restoreFromSaved(
      {
        results: {
          qwen: { success: true, spec: { topic: 'library' }, elapsed: 1 },
        },
        selectedModel: 'qwen',
      },
      'mindmap'
    )

    expect(store.hasAnyResults).toBe(false)
    expect(store.selectedModel).toBeNull()
    expect(store.isGenerating).toBe(true)
  })

  it('does not overwrite a fresh DeepSeek spec with the stale canvas mid-generate', () => {
    setActivePinia(createPinia())
    const store = useLLMResultsStore()
    store.startGeneration('session-regen', 'mindmap', ['qwen', 'deepseek', 'doubao'])
    store.storeResult('deepseek', {
      success: true,
      spec: { topic: 'FastAPI', children: [{ text: '小学' }] },
      elapsed: 1,
    })
    store.setSelectedModel('deepseek')

    store.updateCurrentModelSpec({
      topic: 'FastAPI',
      nodes: [{ id: 'topic', text: '专家旧图' }],
    })

    expect(store.results.deepseek.spec).toEqual({
      topic: 'FastAPI',
      children: [{ text: '小学' }],
    })
  })
})
