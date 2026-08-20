/**
 * Invitation and internal school code helpers — aligned with server utils/invitations.py.
 */

export const INVITE_SAFE_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
export const ORGANIZATION_NAME_MAX_LENGTH = 200

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

/** Unique internal school code so two similarly named orgs do not 409 on create. */
export function uniqueSchoolCodeFromName(name: string): string {
  const letters = name
    .replace(/[^A-Za-z]/g, '')
    .toUpperCase()
    .slice(0, 8)
  const prefix = letters || 'SCH'
  return `${prefix}-${randomPart(6, INVITE_SAFE_CHARS)}`
}

export function sanitizeOrganizationName(name: string): string {
  return name.trim().slice(0, ORGANIZATION_NAME_MAX_LENGTH)
}

export function defaultOrganizationExpiresAtDate(): string {
  const date = new Date()
  date.setFullYear(date.getFullYear() + 1)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function buildOrganizationInviteLink(siteUrl: string, invitationCode: string): string {
  const base = siteUrl.replace(/\/$/, '')
  const code = normalizeInvitationCodeInput(invitationCode)
  if (!base || !code) {
    return ''
  }
  return `${base}/auth?invite=${encodeURIComponent(code)}`
}

export function invitationCodeFromSearch(search: string): string {
  const query = search.startsWith('?') ? search.slice(1) : search
  const raw = new URLSearchParams(query).get('invite')
  if (!raw) {
    return ''
  }
  const code = normalizeInvitationCodeInput(raw)
  return isValidInvitationCode(code) ? code : ''
}
