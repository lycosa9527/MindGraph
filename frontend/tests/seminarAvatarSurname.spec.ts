import { describe, expect, it } from 'vitest'

import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

describe('seminarAvatarSurname', () => {
  it('uses the first CJK character as the surname', () => {
    expect(seminarAvatarSurname('王雅萱')).toBe('王')
    expect(seminarAvatarSurname('  欧阳娜娜  ')).toBe('欧')
  })

  it('uses the last Latin token initial', () => {
    expect(seminarAvatarSurname('Ada Lovelace')).toBe('L')
    expect(seminarAvatarSurname('alice')).toBe('A')
  })

  it('falls back when the name is empty', () => {
    expect(seminarAvatarSurname('')).toBe('?')
    expect(seminarAvatarSurname(null)).toBe('?')
  })

  it('picks a stable tone for the same seed', () => {
    expect(seminarAvatarTone(42)).toEqual(seminarAvatarTone(42))
    expect(seminarAvatarTone('王雅萱').background).toMatch(/^#/)
  })
})
