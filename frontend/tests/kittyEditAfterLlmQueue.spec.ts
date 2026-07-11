import { describe, expect, it } from 'vitest'

import {
  buildKittyEditQueuedForLlmMessage,
  joinDisplayNames,
  listInFlightAutocompleteDisplayNames,
} from '@/composables/kitty/kittyEditAfterLlmQueue'
import type { ModelLoadPhase, ModelState } from '@/stores/llmResults'

describe('kittyEditAfterLlmQueue helpers', () => {
  it('lists in-flight model display names', () => {
    const states: Record<string, ModelState> = {
      qwen: 'ready',
      deepseek: 'loading',
      doubao: 'loading',
    }
    const phases: Record<string, ModelLoadPhase> = {
      qwen: 'ready',
      deepseek: 'streaming',
      doubao: 'waiting',
    }
    expect(listInFlightAutocompleteDisplayNames(states, phases)).toEqual([
      'DeepSeek',
      'Doubao',
    ])
  })

  it('joins names for zh and en', () => {
    expect(joinDisplayNames(['Qwen', 'Doubao'], 'zh')).toBe('Qwen 和 Doubao')
    expect(joinDisplayNames(['Qwen', 'DeepSeek', 'Doubao'], 'en')).toBe(
      'Qwen, DeepSeek, and Doubao'
    )
  })

  it('builds a queued busy message with model names', () => {
    const message = buildKittyEditQueuedForLlmMessage(
      (key, params) => {
        if (key === 'canvas.mindMapOneSentence.kittyEditBusyQueued') {
          return `${params?.models} still streaming — will auto-run`
        }
        return key
      },
      ['Qwen', 'Doubao'],
      'en'
    )
    expect(message).toContain('Qwen and Doubao')
    expect(message).toContain('auto-run')
  })
})
