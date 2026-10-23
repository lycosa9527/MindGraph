import { describe, expect, it } from 'vitest'

import { consultProfileFromAccount } from '@/utils/schoolConsultValidation'

describe('consultProfileFromAccount', () => {
  it('keeps a mainland mobile on the consultation phone field', () => {
    expect(
      consultProfileFromAccount({
        username: 'Ada',
        phone: '13800138000',
        schoolName: 'North School',
      })
    ).toEqual({
      name: 'Ada',
      phone: '13800138000',
      organization: 'North School',
    })
  })

  it('does not copy a 小致 userId into the phone field', () => {
    const uuid = 'ed2d998e-495e-46cc-ab7d-2d64ccba4b92'
    expect(
      consultProfileFromAccount({
        username: uuid,
        phone: uuid,
        schoolName: 'Bayi School',
      })
    ).toEqual({
      name: '',
      phone: '',
      organization: 'Bayi School',
    })
  })
})
