import { describe, expect, it } from 'vitest'

import { resolveDiagramLlmModel } from '@/utils/resolveDiagramLlmModel'

describe('resolveDiagramLlmModel', () => {
  it('returns the selected model when valid', () => {
    expect(resolveDiagramLlmModel('deepseek')).toBe('deepseek')
  })

  it('defaults to qwen when unset or unknown', () => {
    expect(resolveDiagramLlmModel(null)).toBe('qwen')
    expect(resolveDiagramLlmModel('kimi')).toBe('qwen')
  })
})
