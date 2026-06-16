import { describe, expect, it } from 'vitest'

import {
  DEFAULT_USER_AVATAR_EMOJI,
  resolveUserAvatarEmoji,
} from '@/utils/userAvatarEmoji'

describe('resolveUserAvatarEmoji', () => {
  it('returns black cat default for empty, null, and legacy avatar_* values', () => {
    expect(DEFAULT_USER_AVATAR_EMOJI).toBe('🐈‍⬛')
    expect(resolveUserAvatarEmoji(null)).toBe('🐈‍⬛')
    expect(resolveUserAvatarEmoji(undefined)).toBe('🐈‍⬛')
    expect(resolveUserAvatarEmoji('')).toBe('🐈‍⬛')
    expect(resolveUserAvatarEmoji('   ')).toBe('🐈‍⬛')
    expect(resolveUserAvatarEmoji('avatar_01')).toBe('🐈‍⬛')
  })

  it('passes through simple single-codepoint emojis', () => {
    expect(resolveUserAvatarEmoji('😀')).toBe('😀')
    expect(resolveUserAvatarEmoji('👤')).toBe('👤')
    expect(resolveUserAvatarEmoji('🐱')).toBe('🐱')
  })

  it('keeps the brand black cat intact for display', () => {
    expect(resolveUserAvatarEmoji('🐈‍⬛')).toBe('🐈‍⬛')
  })

  it('uses the leading emoji for other ZWJ composites (Edge black-box fix)', () => {
    expect(resolveUserAvatarEmoji('🐻‍❄️')).toBe('🐻')
    expect(resolveUserAvatarEmoji('👩‍🦱')).toBe('👩')
  })

  it('trims stored values before resolving', () => {
    expect(resolveUserAvatarEmoji('  😊  ')).toBe('😊')
  })
})
