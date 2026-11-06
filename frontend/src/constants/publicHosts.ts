/** Canonical public site. Legacy mg is the same app. See utils/public_hosts.py. */

export const CANONICAL_PUBLIC_ORIGIN = 'https://www.mindspringedu.com'

export const CANONICAL_PUBLIC_HOST = 'www.mindspringedu.com'

export const LEGACY_PUBLIC_HOST = 'mg.mindspringedu.com'

export const FIRST_PARTY_PUBLIC_HOSTS = new Set<string>([
  CANONICAL_PUBLIC_HOST,
  LEGACY_PUBLIC_HOST,
])

/** Rewrite a legacy mg origin to https://www. Other hosts stay as given. */
export function rewriteLegacyPublicOrigin(raw: string): string {
  const trimmed = (raw || '').trim().replace(/\/$/, '')
  if (!trimmed) {
    return ''
  }
  let parsed: URL
  try {
    parsed = new URL(trimmed)
  } catch {
    return trimmed
  }
  if (parsed.hostname.toLowerCase() !== LEGACY_PUBLIC_HOST) {
    return trimmed
  }
  parsed.protocol = 'https:'
  parsed.hostname = CANONICAL_PUBLIC_HOST
  if (parsed.port === '80' || parsed.port === '443') {
    parsed.port = ''
  }
  const path = parsed.pathname === '/' ? '' : parsed.pathname
  return `${parsed.origin}${path}${parsed.search}${parsed.hash}`
}
