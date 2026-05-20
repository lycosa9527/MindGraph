import { describe, expect, it } from 'vitest'

import {
  INVITE_CODE_PATTERN,
  INVITE_SAFE_CHARS,
  generateInvitationCode,
  generateRandomSchoolCode,
  generateSchoolCodeFromName,
  isValidInvitationCode,
  normalizeInvitationCodeInput,
  resolveSchoolCodeFromName,
} from '@/utils/invitationCode'

describe('invitationCode utils', () => {
  it('generates invitation codes in XXX-XXX format with safe charset', () => {
    const code = generateInvitationCode()
    expect(code).toMatch(INVITE_CODE_PATTERN)
    expect(code).toHaveLength(7)
    for (const ch of code.replace('-', '')) {
      expect(INVITE_SAFE_CHARS).toContain(ch)
    }
  })

  it('validates invitation codes case-insensitively', () => {
    expect(isValidInvitationCode('abc-234')).toBe(true)
    expect(isValidInvitationCode('ABC-234')).toBe(true)
    expect(isValidInvitationCode('AB-234')).toBe(false)
    expect(isValidInvitationCode('ABC-2345')).toBe(false)
    expect(isValidInvitationCode('AB0-234')).toBe(false)
  })

  it('normalizes invitation input to uppercase trimmed text', () => {
    expect(normalizeInvitationCodeInput('  abc-234  ')).toBe('ABC-234')
  })

  it('derives school code from latin letters in the name', () => {
    expect(generateSchoolCodeFromName('Beijing High School')).toBe('BEIJINGHIGHS')
    expect(generateSchoolCodeFromName('北京市第一中学')).toMatch(/^SCH-[A-Z0-9]{6}$/)
  })

  it('falls back to random school code when name has no latin letters', () => {
    expect(generateRandomSchoolCode()).toMatch(/^SCH-[A-Z0-9]{6}$/)
    expect(resolveSchoolCodeFromName('北京市第一中学')).toMatch(/^SCH-[A-Z0-9]{6}$/)
  })
})
