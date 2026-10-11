import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { loadLocaleMessages } from '@/i18n'
import { authPageSecondaryLocale } from '@/i18n/authPageBilingual'
import { resolveBilingual } from '@/i18n/resolveBilingual'
import { BILINGUAL_UI_KEY } from '@/stores/bilingualUiPrefs'
import { useUIStore } from '@/stores/ui'

describe('auth page bilingual pair', () => {
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
    localStorage.clear()
  })

  it('uses Simplified Chinese under a non-Chinese browser locale', () => {
    expect(authPageSecondaryLocale('en')).toBe('zh')
    expect(authPageSecondaryLocale('ja')).toBe('zh')
  })

  it('stays a single line for Simplified and Traditional Chinese', () => {
    expect(authPageSecondaryLocale('zh')).toBeNull()
    expect(authPageSecondaryLocale('zh-tw')).toBeNull()
  })

  it('shows the slogan in the browser language with Chinese underneath', async () => {
    await loadLocaleMessages('zh')
    const uiStore = useUIStore()
    uiStore.setLanguage('en')
    uiStore.setBilingualUiEnabled(false)
    uiStore.setAuthPageBilingual(true)
    const copy = resolveBilingual('auth.landing.headline')
    expect(copy.primary).toBe('Make every thought clearly visible')
    expect(copy.secondary).toBe('让每一次思考清晰可见')
    expect(localStorage.getItem(BILINGUAL_UI_KEY)).not.toBe('1')
  })

  it('shows only Simplified Chinese when the browser is Simplified Chinese', async () => {
    await loadLocaleMessages('zh')
    const uiStore = useUIStore()
    uiStore.setLanguage('zh')
    uiStore.setAuthPageBilingual(true)
    const copy = resolveBilingual('auth.landing.headline')
    expect(copy.primary).toBe('让每一次思考清晰可见')
    expect(copy.secondary).toBeNull()
  })

  it('shows only Traditional Chinese when the browser is Traditional Chinese', async () => {
    await loadLocaleMessages('zh-tw')
    const uiStore = useUIStore()
    uiStore.setLanguage('zh-tw')
    uiStore.setAuthPageBilingual(true)
    const copy = resolveBilingual('auth.landing.headline')
    expect(copy.primary).toBe('讓每一次思考清晰可見')
    expect(copy.secondary).toBeNull()
  })

  it('keeps Simplified Chinese underneath even when a presenter locale is saved', async () => {
    await loadLocaleMessages('zh')
    await loadLocaleMessages('ja')
    const uiStore = useUIStore()
    uiStore.setLanguage('en')
    uiStore.setBilingualUiEnabled(true)
    uiStore.setPresenterUiLocale('ja')
    uiStore.setAuthPageBilingual(true)
    const copy = resolveBilingual('auth.landing.headline')
    expect(copy.primary).toBe('Make every thought clearly visible')
    expect(copy.secondary).toBe('让每一次思考清晰可见')
    expect(localStorage.getItem(BILINGUAL_UI_KEY)).toBe('1')
  })

  it('does not add a second line on other screens', async () => {
    await loadLocaleMessages('zh')
    const uiStore = useUIStore()
    uiStore.setLanguage('en')
    uiStore.setBilingualUiEnabled(false)
    uiStore.setAuthPageBilingual(false)
    const copy = resolveBilingual('common.save')
    expect(copy.secondary).toBeNull()
  })
})
