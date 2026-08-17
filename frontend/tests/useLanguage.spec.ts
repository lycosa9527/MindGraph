import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useLanguage } from '@/composables/core/useLanguage'
import { i18n } from '@/i18n'

describe('useLanguage', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
    const loc = i18n.global.locale as { value: string }
    loc.value = 'en'
  })

  it('translates without a Vue setup instance (no MUST_BE_CALL_SETUP_TOP / SyntaxError: 26)', () => {
    const { t } = useLanguage()
    expect(t('canvas.mindMapNodeExplain.titleFallback')).toBe('Node explanation')
  })

  it('returns the string fallback when the key is missing', () => {
    const { t } = useLanguage()
    expect(t('canvas.mindMapNodeExplain.notARealKey', 'Meaning')).toBe('Meaning')
  })
})
