import { describe, expect, it } from 'vitest'

import {
  getLocalesForInterfaceLanguagePicker,
  INTERFACE_LANGUAGE_PICKER_CODES,
  INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT,
} from '@/i18n/locales'

describe('interface language picker', () => {
  it('lists the four major Dravidian locales', () => {
    expect(INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT).toBe(INTERFACE_LANGUAGE_PICKER_CODES.length)
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
