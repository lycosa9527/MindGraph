/**
 * School product-term hard lockout (organization_expired).
 *
 * Backend 403 detail: { code, message, school_name, expires_at }.
 * UI: SwissWarningModal in App.vue.
 */
import { eventBus } from '@/composables/core/useEventBus'

export const SCHOOL_EXPIRED_CODE = 'organization_expired'

export type SchoolExpiredInfo = {
  schoolName: string
  expiresAt: string
  message: string
}

let lockoutEmitted = false

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

function parseExpiredObject(detail: Record<string, unknown>): SchoolExpiredInfo | null {
  if (detail.code !== SCHOOL_EXPIRED_CODE) {
    return null
  }
  return {
    schoolName: typeof detail.school_name === 'string' ? detail.school_name : '',
    expiresAt: typeof detail.expires_at === 'string' ? detail.expires_at : '',
    message: typeof detail.message === 'string' ? detail.message : '',
  }
}

function parseExpiredString(detail: string): SchoolExpiredInfo | null {
  const lowered = detail.toLowerCase()
  if (lowered.includes(SCHOOL_EXPIRED_CODE)) {
    return { schoolName: '', expiresAt: '', message: detail }
  }
  if (lowered.includes('subscription') && lowered.includes('expired')) {
    return { schoolName: '', expiresAt: '', message: detail }
  }
  if (detail.includes('订阅') && (detail.includes('到期') || detail.includes('过期'))) {
    return { schoolName: '', expiresAt: '', message: detail }
  }
  return null
}

export function parseSchoolExpiredPayload(payload: unknown): SchoolExpiredInfo | null {
  const root = asRecord(payload)
  if (!root) {
    return null
  }
  const nested = root.detail
  if (typeof nested === 'string') {
    return parseExpiredString(nested)
  }
  const nestedRecord = asRecord(nested)
  if (nestedRecord) {
    return parseExpiredObject(nestedRecord)
  }
  return parseExpiredObject(root)
}

export function isSchoolExpiredPayload(payload: unknown): boolean {
  return parseSchoolExpiredPayload(payload) !== null
}

export function resetSchoolExpiredLockoutEmit(): void {
  lockoutEmitted = false
}

export function emitSchoolExpiredLockout(info: SchoolExpiredInfo): void {
  if (lockoutEmitted) {
    return
  }
  lockoutEmitted = true
  eventBus.emit('auth:school_expired', info)
}

export function emitSchoolExpiredFromPayload(payload: unknown): boolean {
  const info = parseSchoolExpiredPayload(payload)
  if (!info) {
    return false
  }
  emitSchoolExpiredLockout(info)
  return true
}
