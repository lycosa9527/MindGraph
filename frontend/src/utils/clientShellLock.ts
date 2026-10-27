/**
 * Locked mobile/desktop shell for this browser.
 * Null means automatic detection. A stored value overrides viewport and user agent,
 * including after the tablet rotates.
 */
import { shallowRef } from 'vue'

export type ClientShell = 'mobile' | 'desktop'

export const CLIENT_SHELL_STORAGE_KEY = 'mindgraph_client_shell'

export function parseClientShell(value: string | null | undefined): ClientShell | null {
  if (value === 'mobile' || value === 'desktop') return value
  return null
}

function readStoredClientShell(): ClientShell | null {
  if (typeof localStorage === 'undefined') return null
  try {
    return parseClientShell(localStorage.getItem(CLIENT_SHELL_STORAGE_KEY))
  } catch {
    return null
  }
}

/** Null until the user chooses a shell on this device. */
export const clientShellLock = shallowRef<ClientShell | null>(readStoredClientShell())

/**
 * Apply a locked shell over automatic detection.
 * Office embed is handled by the caller and stays desktop.
 */
export function resolveLockedMobile(autoDetected: boolean): boolean {
  if (clientShellLock.value === 'mobile') return true
  if (clientShellLock.value === 'desktop') return false
  return autoDetected
}

export function writeClientShellLock(shell: ClientShell): void {
  clientShellLock.value = shell
  try {
    localStorage.setItem(CLIENT_SHELL_STORAGE_KEY, shell)
  } catch {
    // Private mode can reject storage; the in-memory lock still applies this session.
  }
}

export function resetClientShellLockForTests(): void {
  clientShellLock.value = null
  try {
    localStorage.removeItem(CLIENT_SHELL_STORAGE_KEY)
  } catch {
    // Storage may be unavailable in the test environment.
  }
}
