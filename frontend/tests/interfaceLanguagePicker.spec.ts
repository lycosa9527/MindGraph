import { describe, expect, it } from 'vitest'

import {
  getLocalesForInterfaceLanguagePicker,
  INTERFACE_LANGUAGE_PICKER_CODES,
  INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT,
} from '@/i18n/locales'
import { SUPPORTED_UI_LOCALES } from '@/i18n/supportedUiLocales'

describe('interface language picker', () => {
  it('keeps Settings / landing / mobile on the same 32 translated locales', () => {
    expect(INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT).toBe(32)
    expect(INTERFACE_LANGUAGE_PICKER_CODES).toHaveLength(32)
    const rows = getLocalesForInterfaceLanguagePicker()
    expect(new Set(rows.map((entry) => entry.code))).toEqual(
      new Set(INTERFACE_LANGUAGE_PICKER_CODES)
    )
    for (const code of INTERFACE_LANGUAGE_PICKER_CODES) {
      const registry = SUPPORTED_UI_LOCALES.find((entry) => entry.code === code)
      expect(registry?.enabled).toBe(true)
    }
  })

  it('lists the four major Dravidian locales', () => {
    const rows = getLocalesForInterfaceLanguagePicker()
    const expectRow = (code: string, nativeName: string, englishName: string) => {
      expect(INTERFACE_LANGUAGE_PICKER_CODES).toContain(code)
      const row = rows.find((entry) => entry.code === code)
      expect(row?.nativeName).toBe(nativeName)
      expect(row?.englishName).toBe(englishName)
    }
    expectRow('ta', 'தமிழ்', 'Tamil')
    expectRow('te', 'తెలుగు', 'Telugu')
    expectRow('kn', 'ಕನ್ನಡ', 'Kannada')
    expectRow('ml', 'മലയാളം', 'Malayalam')
  })
})
