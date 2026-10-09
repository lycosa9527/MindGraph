import { describe, expect, it } from 'vitest'

import {
  getLocalesForInterfaceLanguagePicker,
  INTERFACE_LANGUAGE_PICKER_CODES,
  INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT,
} from '@/i18n/locales'
import { SUPPORTED_UI_LOCALES } from '@/i18n/supportedUiLocales'

describe('interface language picker', () => {
  it('keeps Settings / landing / mobile on the same 44 translated locales', () => {
    expect(INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT).toBe(44)
    expect(INTERFACE_LANGUAGE_PICKER_CODES).toHaveLength(44)
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

  it('lists Norwegian under its native name', () => {
    const rows = getLocalesForInterfaceLanguagePicker()
    expect(INTERFACE_LANGUAGE_PICKER_CODES).toContain('no')
    const row = rows.find((entry) => entry.code === 'no')
    expect(row?.nativeName).toBe('Norsk')
    expect(row?.englishName).toBe('Norwegian')
  })

  it('lists the other major European locales', () => {
    const rows = getLocalesForInterfaceLanguagePicker()
    const expectRow = (code: string, nativeName: string, englishName: string) => {
      expect(INTERFACE_LANGUAGE_PICKER_CODES).toContain(code)
      const row = rows.find((entry) => entry.code === code)
      expect(row?.nativeName).toBe(nativeName)
      expect(row?.englishName).toBe(englishName)
    }
    expectRow('sv', 'Svenska', 'Swedish')
    expectRow('da', 'Dansk', 'Danish')
    expectRow('fi', 'Suomi', 'Finnish')
    expectRow('cs', 'Čeština', 'Czech')
    expectRow('sk', 'Slovenčina', 'Slovak')
    expectRow('ro', 'Română', 'Romanian')
    expectRow('hu', 'Magyar', 'Hungarian')
    expectRow('el', 'Ελληνικά', 'Greek')
    expectRow('bg', 'Български', 'Bulgarian')
    expectRow('hr', 'Hrvatski', 'Croatian')
    expectRow('sr', 'Српски', 'Serbian')
  })
})
