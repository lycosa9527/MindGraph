/**
 * Look up a platform user by phone for cross-school seminar invites.
 */
import { authFetch } from '@/utils/api'

export interface SeminarPhoneLookupHit {
  userId: number
  name: string
  avatar: string | null
  orgName: string
  phoneMasked: string
  sameOrg: boolean
}

export function normalizeSeminarPhone(raw: string): string {
  return raw.replace(/\D/g, '').slice(0, 11)
}

export function isValidSeminarPhone(phone: string): boolean {
  return /^1\d{10}$/.test(phone)
}

export async function lookupSeminarUserByPhone(
  phone: string
): Promise<SeminarPhoneLookupHit | null> {
  const normalized = normalizeSeminarPhone(phone)
  if (!isValidSeminarPhone(normalized)) {
    return null
  }
  let response: Response
  try {
    response = await authFetch(
      `/api/mindmate/collab/lookup-phone?phone=${encodeURIComponent(normalized)}`
    )
  } catch {
    return null
  }
  if (response.status === 404) {
    return null
  }
  if (!response.ok) {
    throw new Error('lookup_failed')
  }
  const body = (await response.json()) as {
    id?: number
    name?: string
    avatar?: string | null
    org_name?: string
    phone_masked?: string
    same_org?: boolean
  }
  const userId = Number(body.id)
  if (!Number.isFinite(userId) || userId <= 0) {
    return null
  }
  return {
    userId,
    name: String(body.name || '').trim() || `User ${userId}`,
    avatar: typeof body.avatar === 'string' && body.avatar.trim() ? body.avatar.trim() : null,
    orgName: String(body.org_name || '').trim(),
    phoneMasked: String(body.phone_masked || '').trim(),
    sameOrg: Boolean(body.same_org),
  }
}
