import { describe, expect, it } from 'vitest'

import {
  USER_COLORS,
  USER_EMOJIS,
  colorForUser,
  emojiForUser,
  lockRingColorForUser,
} from '@/shared/collabPalette'

describe('collabPalette', () => {
  it('keeps at least 20 paired colors and emoji', () => {
    expect(USER_COLORS.length).toBeGreaterThanOrEqual(20)
    expect(USER_EMOJIS.length).toBe(USER_COLORS.length)
    expect(new Set(USER_COLORS).size).toBe(USER_COLORS.length)
  })

  it('assigns a stable color per user id', () => {
    expect(colorForUser(1)).toBe(USER_COLORS[1])
    expect(colorForUser(1)).toBe(colorForUser(1 + USER_COLORS.length))
    expect(colorForUser(2)).not.toBe(colorForUser(1))
  })

  it('uses the session color for the lock ring when present', () => {
    expect(lockRingColorForUser(1, '#4ECDC4')).toBe('#4ECDC4')
    expect(lockRingColorForUser(1, '  #FF6B6B  ')).toBe('#FF6B6B')
  })

  it('falls back to the assigned palette color when the session color is missing', () => {
    expect(lockRingColorForUser(1, '')).toBe(colorForUser(1))
    expect(lockRingColorForUser(1, null)).toBe(colorForUser(1))
    expect(lockRingColorForUser(3)).toBe(colorForUser(3))
  })

  it('assigns a matching emoji from the same user index', () => {
    expect(emojiForUser(0)).toBeTruthy()
    expect(emojiForUser(1)).not.toBe(emojiForUser(2))
  })
})
