/** Vitest: lazy locale loading */
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  EAGER_LOCALES,
  i18n,
  isLocaleLoaded,
  loadLocaleMessages,
  setI18nLocale,
} from '@/i18n'
import { LOCALE_EN_COPY_CODES } from '@/i18n/lazyLocaleLoaders'
import { translateForUiLocale } from '@/i18n/translateForUiLocale'

describe('loadLocaleMessages', () => {
  beforeEach(async () => {
    await loadLocaleMessages('zh')
    setI18nLocale('zh')
  })

  it('marks en as eager-loaded; zh loads via loadLocaleMessages', () => {
    expect(EAGER_LOCALES).toEqual(['en'])
    expect(isLocaleLoaded('en')).toBe(true)
    expect(isLocaleLoaded('zh')).toBe(true)
  })

  it('is idempotent for eager locales', async () => {
    await loadLocaleMessages('en')
    await loadLocaleMessages('en')
    expect(isLocaleLoaded('en')).toBe(true)
  })

  it('registers lazy locale messages after load', async () => {
    const wasLoaded = isLocaleLoaded('fr')
    if (!wasLoaded) {
      await loadLocaleMessages('fr')
    }
    expect(isLocaleLoaded('fr')).toBe(true)
    const bundle = i18n.global.getLocaleMessage('fr') as Record<string, unknown>
    expect(Object.keys(bundle).length).toBeGreaterThan(0)
  })

  it('classifies tn as en-copy and fr as dedicated', () => {
    expect(LOCALE_EN_COPY_CODES).toContain('tn')
    expect(LOCALE_EN_COPY_CODES).not.toContain('fr')
  })

  it('loads en-copy locale (tn) with the same strings as en', async () => {
    await loadLocaleMessages('tn')
    const enBundle = i18n.global.getLocaleMessage('en') as Record<string, string>
    const tnBundle = i18n.global.getLocaleMessage('tn') as Record<string, string>
    expect(tnBundle['app.brandName']).toBe(enBundle['app.brandName'])
    expect(tnBundle['mindmate.welcome']).toBe(enBundle['mindmate.welcome'])
  })

  it('loads dedicated fr bundle separately from en-copy path', async () => {
    await loadLocaleMessages('fr')
    const enBundle = i18n.global.getLocaleMessage('en') as Record<string, string>
    const frBundle = i18n.global.getLocaleMessage('fr') as Record<string, string>
    expect(Object.keys(frBundle).length).toBeGreaterThan(0)
    expect(frBundle).not.toBe(enBundle)
  })

  it('translateForUiLocale falls back to English for unloaded locale keys', () => {
    const enText = translateForUiLocale('app.brandName', 'en')
    const unknownText = translateForUiLocale('app.brandName', 'af')
    expect(typeof enText).toBe('string')
    expect(enText.length).toBeGreaterThan(0)
    expect(unknownText).toBe(enText)
  })
})

describe('language switch sequence guard', () => {
  it('applies only the latest async locale switch', async () => {
    let seq = 0
    let activeLocale = 'zh'

    const applyIfLatest = (next: string, switchSeq: number): void => {
      if (switchSeq !== seq) {
        return
      }
      activeLocale = next
    }

    const switchLanguage = (next: string): void => {
      seq += 1
      const mySeq = seq
      void loadLocaleMessages(next as 'fr' | 'de' | 'zh').then(() => {
        applyIfLatest(next, mySeq)
      })
    }

    switchLanguage('fr')
    switchLanguage('de')
    await vi.waitFor(() => {
      expect(activeLocale).toBe('de')
    })
  })
})
