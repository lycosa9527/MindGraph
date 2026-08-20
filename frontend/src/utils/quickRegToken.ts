/**
 * Quick-registration channel token in the URL and sessionStorage.
 * Storage survives an /auth refresh after the query string is stripped.
 */
const STORAGE_KEY = 'mg.quickReg.channelToken'
const MIN_TOKEN_LEN = 20
const MAX_TOKEN_LEN = 512

export function normalizeQuickRegToken(raw: string | null | undefined): string {
  const token = (raw ?? '').trim()
  if (token.length < MIN_TOKEN_LEN || token.length > MAX_TOKEN_LEN) {
    return ''
  }
  return token
}

export function readStoredQuickRegToken(): string {
  try {
    return normalizeQuickRegToken(sessionStorage.getItem(STORAGE_KEY))
  } catch {
    return ''
  }
}

export function writeStoredQuickRegToken(token: string): void {
  const normalized = normalizeQuickRegToken(token)
  try {
    if (!normalized) {
      sessionStorage.removeItem(STORAGE_KEY)
      return
    }
    sessionStorage.setItem(STORAGE_KEY, normalized)
  } catch {
    /* private mode / quota */
  }
}

export function clearStoredQuickRegToken(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* private mode */
  }
}

export function extractQuickRegTokenFromSearch(search: string): string {
  try {
    const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)
    return normalizeQuickRegToken(params.get('quick_reg'))
  } catch {
    return ''
  }
}

export function extractQuickRegTokenFromRedirect(redirect: string, origin: string): string {
  if (!redirect) {
    return ''
  }
  try {
    const pathForUrl = redirect.startsWith('http')
      ? redirect
      : `${origin}${redirect.startsWith('/') ? '' : '/'}${redirect}`
    const parsed = new URL(pathForUrl)
    return normalizeQuickRegToken(parsed.searchParams.get('quick_reg'))
  } catch {
    return ''
  }
}
