/**
 * Invitation and internal school code helpers — aligned with server utils/invitations.py.
 */

export const INVITE_SAFE_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'

export const INVITE_CODE_PATTERN =
  /^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{3}-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{3}$/

function randomPart(length: number, charset: string): string {
  return Array.from({ length }, () => charset[Math.floor(Math.random() * charset.length)]).join('')
}

export function generateInvitationCode(): string {
  return `${randomPart(3, INVITE_SAFE_CHARS)}-${randomPart(3, INVITE_SAFE_CHARS)}`
}

export function isValidInvitationCode(code: string): boolean {
  return INVITE_CODE_PATTERN.test(code.trim().toUpperCase())
}

export function normalizeInvitationCodeInput(code: string): string {
  return code.trim().toUpperCase()
}

export function generateRandomSchoolCode(): string {
  return `SCH-${randomPart(6, INVITE_SAFE_CHARS)}`
}

export function generateSchoolCodeFromName(name: string): string {
  const letters = name.replace(/[^A-Za-z]/g, '').toUpperCase()
  if (letters.length > 0) {
    return letters.slice(0, 12)
  }
  return generateRandomSchoolCode()
}

export function resolveSchoolCodeFromName(name: string): string {
  return generateSchoolCodeFromName(name) || generateRandomSchoolCode()
}
