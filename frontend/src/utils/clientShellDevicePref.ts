/**
 * Client shell is bound to this browser's device cookie, not only the account.
 * The cookie is httpOnly and sent only to /api/auth.
 */
import { parseClientShell } from '@/utils/clientShellLock'
import type { ClientShell } from '@/utils/clientShellLock'

const CLIENT_SHELL_PATH = '/api/auth/client-shell'

export type ClientShellFetch = ClientShell | 'missing' | 'unavailable'

export async function fetchClientShellDevice(): Promise<ClientShellFetch> {
  try {
    const response = await fetch(CLIENT_SHELL_PATH, { credentials: 'same-origin' })
    if (response.status === 404) return 'missing'
    if (!response.ok) return 'unavailable'
    const data = (await response.json()) as { shell?: unknown }
    const shell = parseClientShell(typeof data.shell === 'string' ? data.shell : null)
    return shell ?? 'unavailable'
  } catch {
    return 'unavailable'
  }
}

export async function saveClientShellDevice(shell: ClientShell): Promise<boolean> {
  try {
    const response = await fetch(CLIENT_SHELL_PATH, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ shell }),
    })
    return response.ok
  } catch {
    return false
  }
}
