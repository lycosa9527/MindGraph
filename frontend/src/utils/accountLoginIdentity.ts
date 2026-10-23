/**
 * Login identity shown in account settings.
 * Bayi stores a 小致 userId in the phone column. Mainland accounts use an
 * 11-digit mobile. Overseas accounts store email and leave phone empty.
 * A mainland mobile wins over a secondary email on the same user.
 */
import { isBayiSsoPhone, isCnMainlandMobile } from '@/utils/accountPhone'

export const ACCOUNT_LOGIN_LABEL_KEYS = {
  bayi: 'auth.accountIdBayi',
  mobile: 'auth.accountIdMobile',
  email: 'auth.accountIdEmail',
} as const

export type AccountLoginKind = keyof typeof ACCOUNT_LOGIN_LABEL_KEYS

export type AccountLoginIdentity = {
  kind: AccountLoginKind | 'unset'
  labelKey: (typeof ACCOUNT_LOGIN_LABEL_KEYS)[AccountLoginKind] | 'auth.phone'
  value: string
}

export function displayAccountLoginValue(identity: AccountLoginIdentity): string {
  if (identity.kind === 'mobile') {
    return `${identity.value.slice(0, 3)}****${identity.value.slice(7)}`
  }
  return identity.value
}

export function resolveAccountLoginIdentity(input: {
  phone?: string | null
  email?: string | null
}): AccountLoginIdentity {
  const phone = (input.phone || '').trim()
  const email = (input.email || '').trim()
  if (isBayiSsoPhone(phone)) {
    return { kind: 'bayi', labelKey: ACCOUNT_LOGIN_LABEL_KEYS.bayi, value: phone }
  }
  if (isCnMainlandMobile(phone)) {
    return {
      kind: 'mobile',
      labelKey: ACCOUNT_LOGIN_LABEL_KEYS.mobile,
      value: phone,
    }
  }
  if (email.includes('@')) {
    return { kind: 'email', labelKey: ACCOUNT_LOGIN_LABEL_KEYS.email, value: email }
  }
  if (phone) {
    return { kind: 'unset', labelKey: 'auth.phone', value: phone }
  }
  return { kind: 'unset', labelKey: 'auth.phone', value: '' }
}
