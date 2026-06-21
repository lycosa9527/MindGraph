import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'

import { useLLMResultsStore } from '@/stores/llmResults'

describe('llmResults teardown', () => {
  it('clearCache aborts registered in-flight controllers', () => {
    setActivePinia(createPinia())
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
})
