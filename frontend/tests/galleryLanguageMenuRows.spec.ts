import { describe, expect, it } from 'vitest'

import { getGalleryLanguageMenuRows } from '@/i18n/galleryLanguageMenuRows'
import {
  getLocalesForInterfaceLanguagePicker,
  INTERFACE_LANGUAGE_PICKER_CODES,
  INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT,
} from '@/i18n/locales'

describe('getGalleryLanguageMenuRows', () => {
  it('uses the same 44 codes as Settings → Interface language', () => {
    const landing = getGalleryLanguageMenuRows('en', true).map((row) => row.code)
    const settings = getLocalesForInterfaceLanguagePicker('en', true).map((row) => row.code)
    expect(INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT).toBe(44)
    expect(landing).toHaveLength(44)
    expect(new Set(landing)).toEqual(new Set(settings))
    expect(new Set(landing)).toEqual(new Set(INTERFACE_LANGUAGE_PICKER_CODES))
  })

  it('uses gallery bilingual labels and keeps Chinese native-only', () => {
    const rows = getGalleryLanguageMenuRows('en', true)
    const byCode = Object.fromEntries(rows.map((row) => [row.code, row.label]))
    expect(byCode.en).toBe('English (英语)')
    expect(byCode.zh).toBe('简体中文')
    expect(byCode.ja).toBe('日本語 (日语)')
    expect(byCode.no).toBe('Norsk (挪威语)')
    expect(byCode.sv).toBe('Svenska (瑞典语)')
    expect(byCode.da).toBe('Dansk (丹麦语)')
    expect(byCode.fi).toBe('Suomi (芬兰语)')
    expect(byCode.cs).toBe('Čeština (捷克语)')
    expect(byCode.sk).toBe('Slovenčina (斯洛伐克语)')
    expect(byCode.ro).toBe('Română (罗马尼亚语)')
    expect(byCode.hu).toBe('Magyar (匈牙利语)')
    expect(byCode.el).toBe('Ελληνικά (希腊语)')
    expect(byCode.bg).toBe('Български (保加利亚语)')
    expect(byCode.hr).toBe('Hrvatski (克罗地亚语)')
    expect(byCode.sr).toBe('Српски (塞尔维亚语)')
  })

  it('hides Simplified Chinese when policy disallows it', () => {
    const rows = getGalleryLanguageMenuRows('en', false)
    expect(rows.some((row) => row.code === 'zh')).toBe(false)
    expect(rows.some((row) => row.code === 'en')).toBe(true)
  })
})
