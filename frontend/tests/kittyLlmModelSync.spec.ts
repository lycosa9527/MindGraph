import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  applyKittyRemoteLlmModel,
  normalizeKittyLlmModel,
} from '../src/composables/kitty/applyKittyRemoteLlmModel'
import { useLLMResultsStore } from '../src/stores/llmResults'

describe('normalizeKittyLlmModel', () => {
  it('accepts the three desktop models', () => {
    expect(normalizeKittyLlmModel('qwen')).toBe('qwen')
    expect(normalizeKittyLlmModel('DeepSeek')).toBe('deepseek')
    expect(normalizeKittyLlmModel('DOUBAO')).toBe('doubao')
  })

  it('treats empty/null sentinels as clear', () => {
    expect(normalizeKittyLlmModel(null)).toBe(null)
    expect(normalizeKittyLlmModel('')).toBe(null)
    expect(normalizeKittyLlmModel('none')).toBe(null)
  })

  it('rejects unknown models', () => {
    expect(normalizeKittyLlmModel('gpt')).toBe(null)
  })
})

describe('applyKittyRemoteLlmModel during auto-complete', () => {
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
    setActivePinia(createPinia())
  })

  it('does not reclaim the previous model slot while generating', async () => {
    const store = useLLMResultsStore()
    store.startGeneration('session-regen', 'mindmap', ['qwen', 'deepseek', 'doubao'])
    expect(store.selectedModel).toBeNull()

    const changed = await applyKittyRemoteLlmModel('deepseek')

    expect(changed).toBe(false)
    expect(store.selectedModel).toBeNull()
    expect(store.modelStates.deepseek).toBe('loading')
  })
})
