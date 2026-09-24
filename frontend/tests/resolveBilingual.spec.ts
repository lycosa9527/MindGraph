import { createPinia, setActivePinia } from 'pinia'
import { computed, nextTick } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { isLocaleLoaded, loadLocaleMessages } from '@/i18n'
import { resolveBilingual } from '@/i18n/resolveBilingual'
import { useUIStore } from '@/stores/ui'

describe('resolveBilingual', () => {
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

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns only the primary locale when bilingual mode is off', () => {
    const uiStore = useUIStore()
    uiStore.setLanguage('en')
    uiStore.setBilingualUiEnabled(false)
    uiStore.setPresenterUiLocale('zh')
    const copy = resolveBilingual('common.save')
    expect(copy.primary).toBeTruthy()
    expect(copy.secondary).toBeNull()
  })

  it('hides the second line when presenter locale matches the interface locale', () => {
    const uiStore = useUIStore()
    uiStore.setLanguage('en')
    uiStore.setBilingualUiEnabled(true)
    uiStore.setPresenterUiLocale('en')
    const copy = resolveBilingual('common.save')
    expect(copy.secondary).toBeNull()
  })

  it('returns both lines when locales differ and bilingual mode is on', async () => {
    await loadLocaleMessages('zh')
    const uiStore = useUIStore()
    uiStore.setLanguage('en')
    uiStore.setBilingualUiEnabled(true)
    uiStore.setPresenterUiLocale('zh')
    const copy = resolveBilingual('common.save')
    expect(copy.primary).toBeTruthy()
    expect(copy.secondary).toBeTruthy()
    expect(copy.secondary).not.toBe(copy.primary)
  })

  it('refreshes presenter copy after the lazy locale bundle arrives', async () => {
    const uiStore = useUIStore()
    uiStore.setLanguage('en')
    uiStore.setPresenterUiLocale('ja')
    expect(isLocaleLoaded('ja')).toBe(false)
    const copy = computed(() => resolveBilingual('common.save'))
    uiStore.setBilingualUiEnabled(true)
    expect(copy.value.secondary).toBe('Save')
    await loadLocaleMessages('ja')
    await nextTick()
    expect(copy.value.secondary).toBe('保存')
    expect(copy.value.primary).toBe('Save')
  })
})
