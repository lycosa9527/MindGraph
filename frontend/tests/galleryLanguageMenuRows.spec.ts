import { describe, expect, it } from 'vitest'

import { getGalleryLanguageMenuRows } from '@/i18n/galleryLanguageMenuRows'
import {
  getLocalesForInterfaceLanguagePicker,
  INTERFACE_LANGUAGE_PICKER_CODES,
  INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT,
} from '@/i18n/locales'

describe('getGalleryLanguageMenuRows', () => {
  it('uses the same 32 codes as Settings → Interface language', () => {
    const landing = getGalleryLanguageMenuRows('en', true).map((row) => row.code)
    const settings = getLocalesForInterfaceLanguagePicker('en', true).map((row) => row.code)
    expect(INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT).toBe(32)
    expect(landing).toHaveLength(32)
    expect(new Set(landing)).toEqual(new Set(settings))
    expect(new Set(landing)).toEqual(new Set(INTERFACE_LANGUAGE_PICKER_CODES))
  })

  it('uses gallery bilingual labels and keeps Chinese native-only', () => {
    const rows = getGalleryLanguageMenuRows('en', true)
    const byCode = Object.fromEntries(rows.map((row) => [row.code, row.label]))
    expect(byCode.en).toBe('English (英语)')
    expect(byCode.zh).toBe('简体中文')
    expect(byCode.ja).toBe('日本語 (日语)')
  })

  it('hides Simplified Chinese when policy disallows it', () => {
    const rows = getGalleryLanguageMenuRows('en', false)
    expect(rows.some((row) => row.code === 'zh')).toBe(false)
    expect(rows.some((row) => row.code === 'en')).toBe(true)
  })
})
