import { describe, expect, it } from 'vitest'

import {
  SOFTWARE_AGREEMENT_EN,
  SOFTWARE_AGREEMENT_ZH,
  softwareAgreementForUiCode,
} from '@/content/authSoftwareAgreement'

describe('softwareAgreementForUiCode', () => {
  it('returns Chinese agreement for zh and zh-tw UI', () => {
    expect(softwareAgreementForUiCode('zh')).toBe(SOFTWARE_AGREEMENT_ZH)
    expect(softwareAgreementForUiCode('zh-tw')).toBe(SOFTWARE_AGREEMENT_ZH)
  })

  it('returns English agreement for all other UI locales', () => {
    for (const code of ['en', 'fr', 'ja', 'de', 'az']) {
      expect(softwareAgreementForUiCode(code)).toBe(SOFTWARE_AGREEMENT_EN)
    }
  })
})
