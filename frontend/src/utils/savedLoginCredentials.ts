/**
 * Persist teacher login identifier (phone/email) in localStorage so repeat sign-in
 * prefills the username field. Password is never stored — use browser password manager.
 */

const STORAGE_KEY = 'mg_saved_login_v1'

function parseStoredIdentifier(raw: string): string | null {
  const parsed = JSON.parse(raw) as unknown
  if (typeof parsed === 'string') {
    const trimmed = parsed.trim()
    return trimmed || null
  }
  if (typeof parsed !== 'object' || parsed === null) {
    return null
  }
  const record = parsed as Record<string, unknown>
  if (typeof record.identifier !== 'string') {
    return null
  }
  const identifier = record.identifier.trim()
  return identifier || null
}

export function loadSavedLoginIdentifier(): string | null {
  if (typeof localStorage === 'undefined') {
    return null
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return null
    }
    const identifier = parseStoredIdentifier(raw)
    if (!identifier) {
      return null
    }
    try {
      const parsed = JSON.parse(raw) as unknown
      if (
        typeof parsed === 'object' &&
        parsed !== null &&
        'password' in (parsed as Record<string, unknown>)
      ) {
        saveLoginIdentifier(identifier)
      }
    } catch {
      // ignore legacy purge errors
    }
    return identifier
  } catch {
    return null
  }
}

export function saveLoginIdentifier(identifier: string): void {
  const trimmed = identifier.trim()
  if (!trimmed) {
    return
  }
  if (typeof localStorage === 'undefined') {
    return
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ identifier: trimmed }))
  } catch {
    // Quota or private mode — ignore
  }
}

export function clearSavedLoginCredentials(): void {
  if (typeof localStorage === 'undefined') {
    return
  }
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}
