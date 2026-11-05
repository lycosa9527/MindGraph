/** Canonical public site. Legacy ``mg`` is the same app. See ``utils/public_hosts.py``. */

export const CANONICAL_PUBLIC_ORIGIN = 'https://www.mindspringedu.com'

export const CANONICAL_PUBLIC_HOST = 'www.mindspringedu.com'

export const LEGACY_PUBLIC_HOST = 'mg.mindspringedu.com'

export const FIRST_PARTY_PUBLIC_HOSTS = new Set<string>([
  CANONICAL_PUBLIC_HOST,
  LEGACY_PUBLIC_HOST,
])
