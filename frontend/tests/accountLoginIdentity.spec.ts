import { describe, expect, it } from 'vitest'

import { displayAccountLoginValue, resolveAccountLoginIdentity } from '@/utils/accountLoginIdentity'

describe('resolveAccountLoginIdentity', () => {
  it('shows a 小致 userId as the Bayi account id', () => {
    const uuid = 'ed2d998e-495e-46cc-ab7d-2d64ccba4b92'
    expect(resolveAccountLoginIdentity({ phone: uuid, email: 'also@school.edu' })).toEqual({
      kind: 'bayi',
      labelKey: 'auth.accountIdBayi',
      value: uuid,
    })
  })

  it('keeps a mainland mobile ahead of a secondary email and masks only the display', () => {
    const identity = resolveAccountLoginIdentity({
      phone: '13800138000',
      email: 'teacher@school.edu',
    })
    expect(identity).toEqual({
      kind: 'mobile',
      labelKey: 'auth.accountIdMobile',
      value: '13800138000',
    })
    expect(displayAccountLoginValue(identity)).toBe('138****8000')
  })

  it('shows the email when the account has no phone', () => {
    expect(resolveAccountLoginIdentity({ phone: null, email: 'ada@school.edu' })).toEqual({
      kind: 'email',
      labelKey: 'auth.accountIdEmail',
      value: 'ada@school.edu',
    })
  })

  it('leaves the field empty when neither phone nor email is set', () => {
    expect(resolveAccountLoginIdentity({ phone: '', email: '' })).toEqual({
      kind: 'unset',
      labelKey: 'auth.phone',
      value: '',
    })
  })
})
