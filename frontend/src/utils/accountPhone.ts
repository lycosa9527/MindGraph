/**
 * Account key stored in the phone column: mainland mobile, or a Bayi SSO userId.
 */

const BAYI_SSO_PHONE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function isBayiSsoPhone(phone: string | null | undefined): boolean {
  return BAYI_SSO_PHONE.test((phone || '').trim())
}

export function isCnMainlandMobile(phone: string | null | undefined): boolean {
  const value = (phone || '').trim()
  return value.length === 11 && value.startsWith('1') && /^\d+$/.test(value)
}

/** True when an admin save may keep this value in the phone column. */
export function isAdminAccountPhone(phone: string | null | undefined): boolean {
  return isCnMainlandMobile(phone) || isBayiSsoPhone(phone)
}
