import { describe, expect, it } from 'vitest'

import { softwareAgreementForUiCode } from '@/content/authSoftwareAgreement'
import { textHasSimplifiedChinese, toTraditionalChinese } from '@/utils/simplifiedTraditional'

describe('simplifiedTraditional', () => {
  it('detects simplified glyphs and leaves traditional text unchanged', () => {
    expect(textHasSimplifiedChinese('用户协议')).toBe(true)
    expect(textHasSimplifiedChinese('用戶協議')).toBe(false)
    expect(textHasSimplifiedChinese('hello')).toBe(false)
    expect(textHasSimplifiedChinese('   ')).toBe(false)
  })

  it('converts simplified characters without rewriting shared glyphs', () => {
    expect(toTraditionalChinese('用户协议')).toBe('用戶協議')
    expect(toTraditionalChinese('信息')).toBe('信息')
  })

  it('still produces a traditional agreement title', () => {
    expect(softwareAgreementForUiCode('zh-tw').title).toContain('用戶協議')
  })
})
