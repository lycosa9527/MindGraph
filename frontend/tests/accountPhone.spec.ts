import { describe, expect, it } from 'vitest'

import { isAdminAccountPhone, isBayiSsoPhone, isCnMainlandMobile } from '@/utils/accountPhone'

describe('accountPhone', () => {
  it('accepts a 小致 userId stored as the phone', () => {
    const uuid = 'ed2d998e-495e-46cc-ab7d-2d64ccba4b92'
    expect(isBayiSsoPhone(uuid)).toBe(true)
    expect(isAdminAccountPhone(uuid)).toBe(true)
  })

  it('still accepts an 11-digit mainland mobile', () => {
    expect(isCnMainlandMobile('13800138000')).toBe(true)
    expect(isAdminAccountPhone('13800138000')).toBe(true)
  })

  it('rejects a short or non-numeric phone', () => {
    expect(isAdminAccountPhone('12345')).toBe(false)
    expect(isAdminAccountPhone('not-a-phone')).toBe(false)
  })
})
