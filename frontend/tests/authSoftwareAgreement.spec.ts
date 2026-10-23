import { describe, expect, it } from 'vitest'

import {
  SOFTWARE_AGREEMENT_EN,
  SOFTWARE_AGREEMENT_ZH,
  softwareAgreementForUiCode,
} from '@/content/authSoftwareAgreement'

describe('softwareAgreementForUiCode', () => {
  it('returns Chinese agreement for zh and Traditional text for zh-tw', () => {
    expect(softwareAgreementForUiCode('zh')).toBe(SOFTWARE_AGREEMENT_ZH)
    const traditional = softwareAgreementForUiCode('zh-tw')
    expect(traditional.title).toContain('用戶協議')
    expect(traditional.title).not.toBe(SOFTWARE_AGREEMENT_ZH.title)
  })

  it('returns English agreement for all other UI locales', () => {
    for (const code of ['en', 'fr', 'ja', 'de', 'az']) {
      expect(softwareAgreementForUiCode(code)).toBe(SOFTWARE_AGREEMENT_EN)
    }
  })
})
