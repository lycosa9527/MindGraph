import { describe, expect, it } from 'vitest'

import { canvasMenuModelLabel } from '@/config/canvasLlmMenu'

describe('canvas LLM menu model label', () => {
  it('shows the live model id instead of the marketing name', () => {
    expect(
      canvasMenuModelLabel('express', { express: 'deepseek-v4.1-flash' }, 'DeepSeek Flash')
    ).toBe('deepseek-v4.1-flash')
    expect(
      canvasMenuModelLabel('qwen3-max', { 'qwen3-max': ' qwen3.8-max ' }, 'Qwen Max')
    ).toBe('qwen3.8-max')
    expect(
      canvasMenuModelLabel('kimi', { kimi: 'glm-5-3-flash-260828' }, 'GLM Flash')
    ).toBe('glm-5-3-flash')
    expect(
      canvasMenuModelLabel(
        'doubao21',
        { doubao21: 'doubao-seed-2-1-turbo-260628' },
        '豆包'
      )
    ).toBe('doubao-seed-2-1-turbo')
  })

  it('keeps the translated name when no model id is configured', () => {
    expect(canvasMenuModelLabel('kimi', { kimi: '  ' }, 'GLM Flash')).toBe('GLM Flash')
    expect(canvasMenuModelLabel('doubao21', {}, '豆包')).toBe('豆包')
  })
})