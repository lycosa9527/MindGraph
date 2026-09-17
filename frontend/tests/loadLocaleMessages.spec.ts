/** Vitest: lazy locale loading */
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  EAGER_LOCALES,
  hasLazyLocaleBundle,
  i18n,
  isLocaleLoaded,
  loadLocaleMessages,
  setI18nLocale,
} from '@/i18n'
import { INTERFACE_LANGUAGE_PICKER_CODES, UI_LOCALE_CODES } from '@/i18n/locales'
import { translateForUiLocale } from '@/i18n/translateForUiLocale'
import arMessages from '@/locales/messages/ar'
import deMessages from '@/locales/messages/de'
import esMessages from '@/locales/messages/es'
import jaMessages from '@/locales/messages/ja'
import ptMessages from '@/locales/messages/pt'
import ruMessages from '@/locales/messages/ru'
import siMessages from '@/locales/messages/si'

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

  it('has a glob bundle for every enabled UI locale', () => {
    const uncovered = UI_LOCALE_CODES.filter((code) => !hasLazyLocaleBundle(code))
    expect(uncovered).toEqual([])
  })

  it('loads every enabled UI locale from its message file', async () => {
    const pickerSet = new Set<string>(INTERFACE_LANGUAGE_PICKER_CODES)
    expect(UI_LOCALE_CODES.some((code) => pickerSet.has(code))).toBe(true)
    expect(UI_LOCALE_CODES.some((code) => !pickerSet.has(code))).toBe(true)
    for (const code of UI_LOCALE_CODES) {
      await loadLocaleMessages(code)
      expect(isLocaleLoaded(code), code).toBe(true)
      const bundle = i18n.global.getLocaleMessage(code) as Record<string, unknown>
      expect(Object.keys(bundle).length, code).toBeGreaterThan(0)
    }
  }, 30_000)

  it('ships native UI copy for restored picker locales', () => {
    const enLogin = (i18n.global.getLocaleMessage('en') as Record<string, string>)[
      'app.guestMainLoginPrompt'
    ]
    expect(siMessages['app.guestMainLoginPrompt']).toMatch(/[\u0D80-\u0DFF]/)
    expect(siMessages['app.guestMainLoginPrompt']).not.toBe(enLogin)
    expect(jaMessages['app.guestMainLoginPrompt']).toMatch(/[\u3040-\u30ff\u4e00-\u9fff]/)
    expect(deMessages['app.guestMainLoginPrompt']).toMatch(/Melden Sie sich/)
    expect(esMessages['app.guestMainLoginPrompt']).toMatch(/Inicie sesión/)
    expect(arMessages['app.guestMainLoginPrompt']).toMatch(/[\u0600-\u06FF]/)
    expect(arMessages['app.guestMainLoginPrompt']).not.toBe(enLogin)
    expect(ptMessages['app.guestMainLoginPrompt']).toMatch(/Faça login/)
    expect(ruMessages['app.guestMainLoginPrompt']).toMatch(/[\u0400-\u04FF]/)
  })

  it('loads dedicated fr bundle separately from English', async () => {
    await loadLocaleMessages('fr')
    const enBundle = i18n.global.getLocaleMessage('en') as Record<string, string>
    const frBundle = i18n.global.getLocaleMessage('fr') as Record<string, string>
    expect(Object.keys(frBundle).length).toBeGreaterThan(0)
    expect(frBundle).not.toBe(enBundle)
    expect(frBundle['app.guestMainLoginPrompt']).not.toBe(enBundle['app.guestMainLoginPrompt'])
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
