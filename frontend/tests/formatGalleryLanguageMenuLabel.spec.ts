import { describe, expect, it } from 'vitest'

import { formatGalleryLanguageMenuLabel } from '@/i18n/galleryLanguageMenuLabel'

describe('formatGalleryLanguageMenuLabel', () => {
  it('appends the Chinese name like the caption dropdown', () => {
    expect(formatGalleryLanguageMenuLabel('en', 'English')).toBe('English (英语)')
    expect(formatGalleryLanguageMenuLabel('fr', 'Français')).toBe('Français (法语)')
    expect(formatGalleryLanguageMenuLabel('ja', '日本語')).toBe('日本語 (日语)')
  })

  it('keeps Chinese locales native-only', () => {
    expect(formatGalleryLanguageMenuLabel('zh', '中文')).toBe('中文')
    expect(formatGalleryLanguageMenuLabel('zh-tw', '繁體中文')).toBe('繁體中文')
  })

  it('returns the native label when no Chinese name is known', () => {
    expect(formatGalleryLanguageMenuLabel('xx', 'Unknown')).toBe('Unknown')
  })
})
