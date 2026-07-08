import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  detectPrivacyPageUiCode,
  isBrowserLanguageChinese,
  privacyPageDocumentTitle,
  privacyPageUpdatedLabel,
} from '@/utils/privacyPageLocale'

function mockNavigatorLanguages(languages: string[]) {
  vi.stubGlobal('navigator', {
    language: languages[0] ?? 'en',
    languages,
  })
}

describe('privacyPageLocale', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('isBrowserLanguageChinese', () => {
    it('returns true for zh, zh-CN, and zh-TW', () => {
      mockNavigatorLanguages(['zh-CN'])
      expect(isBrowserLanguageChinese()).toBe(true)

      mockNavigatorLanguages(['zh-TW', 'en'])
      expect(isBrowserLanguageChinese()).toBe(true)

      mockNavigatorLanguages(['zh'])
      expect(isBrowserLanguageChinese()).toBe(true)
    })

    it('returns false for English and other non-Chinese languages', () => {
      mockNavigatorLanguages(['en-US'])
      expect(isBrowserLanguageChinese()).toBe(false)

      mockNavigatorLanguages(['fr', 'de'])
      expect(isBrowserLanguageChinese()).toBe(false)
    })
  })

  describe('detectPrivacyPageUiCode', () => {
    it('maps Chinese browsers to zh and others to en', () => {
      mockNavigatorLanguages(['zh-CN'])
      expect(detectPrivacyPageUiCode()).toBe('zh')

      mockNavigatorLanguages(['ja', 'en'])
      expect(detectPrivacyPageUiCode()).toBe('en')
    })
  })

  it('formats chrome strings for each locale', () => {
    expect(privacyPageUpdatedLabel('zh', '2026年6月19日')).toBe('更新日期：2026年6月19日')
    expect(privacyPageUpdatedLabel('en', 'June 19, 2026')).toBe('Last updated: June 19, 2026')
    expect(privacyPageDocumentTitle('zh')).toBe('用户协议与隐私政策 · 迈特教研')
    expect(privacyPageDocumentTitle('en')).toBe('Terms & Privacy · Mind Platform')
  })
})
