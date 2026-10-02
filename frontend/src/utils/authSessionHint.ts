/**
 * Survives browser restart so a still-valid refresh cookie can be used.
 * The flag is not a credential: tokens stay in httpOnly cookies.
 */
export const AUTH_SESSION_HINT_KEY = 'mg_auth_session'

export function markAuthSessionHint(): void {
  try {
    localStorage.setItem(AUTH_SESSION_HINT_KEY, '1')
  } catch {
    // Private mode or a full storage quota — cookies still carry the session.
  }
}

export function clearAuthSessionHint(): void {
  try {
    localStorage.removeItem(AUTH_SESSION_HINT_KEY)
  } catch {
    // Ignore storage failures; the next login rewrites the hint.
  }
}

export function hasAuthSessionHint(): boolean {
  try {
    return localStorage.getItem(AUTH_SESSION_HINT_KEY) === '1'
  } catch {
    return false
  }
}
