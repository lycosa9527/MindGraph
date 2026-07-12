import { describe, expect, it } from 'vitest'

import { normalizeKittyLlmModel } from '../src/composables/kitty/applyKittyRemoteLlmModel'

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
