import { describe, expect, it } from 'vitest'

import { resolveDiagramLlmModel } from '@/utils/resolveDiagramLlmModel'

describe('resolveDiagramLlmModel', () => {
  it('returns the selected model when valid', () => {
    expect(resolveDiagramLlmModel('deepseek')).toBe('deepseek')
  })

  it('keeps a menu id and defaults when unset or unknown', () => {
    expect(resolveDiagramLlmModel('kimi')).toBe('kimi')
    expect(resolveDiagramLlmModel(null)).toBe('express')
    expect(resolveDiagramLlmModel('not-a-model')).toBe('express')
  })
})
