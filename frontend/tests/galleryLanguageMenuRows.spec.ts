import { describe, expect, it } from 'vitest'

import { getGalleryLanguageMenuRows } from '@/i18n/galleryLanguageMenuRows'

describe('getGalleryLanguageMenuRows', () => {
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
