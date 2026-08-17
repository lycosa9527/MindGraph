import { describe, expect, it, vi } from 'vitest'

import { safeI18nTranslate } from '@/utils/safeI18nTranslate'

describe('safeI18nTranslate', () => {
  it('returns the translator result', () => {
    expect(safeI18nTranslate(() => '节点解释', 'canvas.mindMapNodeExplain.titleFallback')).toBe(
      '节点解释'
    )
  })

  it('uses the string fallback when the key is missing', () => {
    expect(safeI18nTranslate((key) => key, 'missing.key', 'fallback')).toBe('fallback')
  })

  it('passes named interpolation through', () => {
    const translate = vi.fn((_key: string, named?: Record<string, unknown>) => `n=${named?.n}`)
    expect(safeI18nTranslate(translate, 'k', { n: 3 })).toBe('n=3')
    expect(translate).toHaveBeenCalledWith('k', { n: 3 })
  })

  it('returns the key when the translator throws', () => {
    const translate = (): never => {
      throw new SyntaxError('26')
    }
    expect(safeI18nTranslate(translate, 'canvas.mindMapNodeExplain.panelMeaning')).toBe(
      'canvas.mindMapNodeExplain.panelMeaning'
    )
  })

  it('returns the string fallback when compile throws', () => {
    const translate = (): never => {
      throw new SyntaxError('26')
    }
    expect(safeI18nTranslate(translate, 'bad.key', 'Meaning')).toBe('Meaning')
  })
})
