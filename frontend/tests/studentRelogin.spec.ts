import { afterEach, describe, expect, it } from 'vitest'

import { stashStudentRelogin, takeStudentRelogin } from '@/utils/studentRelogin'

describe('studentRelogin', () => {
  afterEach(() => {
    sessionStorage.clear()
  })

  it('returns the stashed class code, name, and saved flag once', () => {
    stashStudentRelogin({ classCode: 'AB12', name: '王王', passwordSaved: true })
    expect(takeStudentRelogin()).toEqual({
      classCode: 'AB12',
      name: '王王',
      passwordSaved: true,
    })
    expect(takeStudentRelogin()).toBeNull()
  })

  it('drops a corrupt payload', () => {
    sessionStorage.setItem('mg_student_password_relogin', '{')
    expect(takeStudentRelogin()).toBeNull()
  })
})
