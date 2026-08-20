import { describe, expect, it } from 'vitest'

import {
  INVITE_CODE_PATTERN,
  INVITE_SAFE_CHARS,
  ORGANIZATION_NAME_MAX_LENGTH,
  buildOrganizationInviteLink,
  defaultOrganizationExpiresAtDate,
  generateInvitationCode,
  generateRandomSchoolCode,
  generateSchoolCodeFromName,
  invitationCodeFromSearch,
  isValidInvitationCode,
  normalizeInvitationCodeInput,
  resolveSchoolCodeFromName,
  sanitizeOrganizationName,
  uniqueSchoolCodeFromName,
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

  it('builds an auth invite link from site url and code', () => {
    expect(buildOrganizationInviteLink('https://mindgraph.example/', 'abc-234')).toBe(
      'https://mindgraph.example/auth?invite=ABC-234'
    )
    expect(buildOrganizationInviteLink('', 'ABC-234')).toBe('')
  })

  it('reads a valid invite code from the auth query string', () => {
    expect(invitationCodeFromSearch('?invite=abc-234')).toBe('ABC-234')
    expect(invitationCodeFromSearch('invite=AB0-234')).toBe('')
    expect(invitationCodeFromSearch('')).toBe('')
    expect(invitationCodeFromSearch(`?invite=${encodeURIComponent('abc-234')}`)).toBe('ABC-234')
    expect(invitationCodeFromSearch('?invite=abc-234%26extra=1')).toBe('')
  })

  it('builds unique school codes so similarly named orgs do not collide', () => {
    const first = uniqueSchoolCodeFromName('Beijing High School')
    const second = uniqueSchoolCodeFromName('Beijing High School')
    expect(first).toMatch(/^BEIJINGH-[A-Z0-9]{6}$/)
    expect(second).toMatch(/^BEIJINGH-[A-Z0-9]{6}$/)
    expect(first).not.toBe(second)
    expect(uniqueSchoolCodeFromName('北京市第一中学')).toMatch(/^SCH-[A-Z0-9]{6}$/)
  })

  it('trims and caps organization names at the database limit', () => {
    expect(sanitizeOrganizationName('  Demo  ')).toBe('Demo')
    expect(sanitizeOrganizationName('x'.repeat(ORGANIZATION_NAME_MAX_LENGTH + 20))).toHaveLength(
      ORGANIZATION_NAME_MAX_LENGTH
    )
  })

  it('defaults organization expiry to one year from today', () => {
    const expiry = defaultOrganizationExpiresAtDate()
    expect(expiry).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    const expected = new Date()
    expected.setFullYear(expected.getFullYear() + 1)
    const year = expected.getFullYear()
    const month = String(expected.getMonth() + 1).padStart(2, '0')
    const day = String(expected.getDate()).padStart(2, '0')
    expect(expiry).toBe(`${year}-${month}-${day}`)
  })
})
