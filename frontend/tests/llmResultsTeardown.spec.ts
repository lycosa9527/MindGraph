import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { shouldSkipLibraryReloadDuringGeneration } from '@/composables/canvasPage/skipLibraryReloadDuringGeneration'
import { useLLMResultsStore } from '@/stores/llmResults'

describe('shouldSkipLibraryReloadDuringGeneration', () => {
  it('skips when generating and route id matches active diagram', () => {
    expect(shouldSkipLibraryReloadDuringGeneration(true, 'diag-1', 'diag-1')).toBe(true)
  })

  it('does not skip when generating but switching to another diagram', () => {
    expect(shouldSkipLibraryReloadDuringGeneration(true, 'diag-2', 'diag-1')).toBe(false)
  })

  it('does not skip when not generating', () => {
    expect(shouldSkipLibraryReloadDuringGeneration(false, 'diag-1', 'diag-1')).toBe(false)
  })

  it('does not skip when active diagram is unset', () => {
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
