/**
 * Locked interface shell for this browser.
 * Local storage paints immediately. The signed-in device row in Postgres wins.
 */
import { useUIStore } from '@/stores/ui'
import { fetchClientShellDevice, saveClientShellDevice } from '@/utils/clientShellDevicePref'
import type { ClientShellFetch } from '@/utils/clientShellDevicePref'
import { clientShellLock, writeClientShellLock } from '@/utils/clientShellLock'
import type { ClientShell } from '@/utils/clientShellLock'

/** Choices made on this page. A later login writes them instead of restoring an older row. */
let localEdits = 0

export type ClientShellHydratePlan = 'ignore' | 'upload-local' | 'apply-remote'

/**
 * Server row wins only when this page has not chosen a shell during the request.
 * A missing row uploads the local lock. An in-flight choice is left alone so an
 * older response cannot replace it.
 */
export function planClientShellHydrate(
  editsAtStart: number,
  editsNow: number,
  remote: ClientShellFetch,
  local: ClientShell | null
): ClientShellHydratePlan {
  if (editsNow !== editsAtStart || remote === 'unavailable') return 'ignore'
  if (remote === 'missing') return local ? 'upload-local' : 'ignore'
  if (editsAtStart > 0) return 'ignore'
  return 'apply-remote'
}

export async function commitClientShell(shell: ClientShell): Promise<boolean> {
  if (clientShellLock.value === shell) return true
  localEdits += 1
  const saved = await saveClientShellDevice(shell)
  if (!saved) {
    localEdits -= 1
    return false
  }
  writeClientShellLock(shell)
  useUIStore().checkMobile()
  return true
}

/**
 * The device row wins when this page has not changed the segment.
 * A choice made before login is written so the tablet lock is recorded.
 */
export async function hydrateClientShellFromDevice(): Promise<void> {
  const editsAtStart = localEdits
  const remote = await fetchClientShellDevice()
  const plan = planClientShellHydrate(editsAtStart, localEdits, remote, clientShellLock.value)
  if (plan === 'ignore') return
  if (plan === 'upload-local') {
    const shell = clientShellLock.value
    if (!shell) return
    await saveClientShellDevice(shell)
    const latest = clientShellLock.value
    if (latest && latest !== shell && localEdits !== editsAtStart) {
      await saveClientShellDevice(latest)
    }
    return
  }
  if (localEdits !== editsAtStart || remote === 'missing' || remote === 'unavailable') return
  writeClientShellLock(remote)
  useUIStore().checkMobile()
}

export function resetClientShellEditsForTests(): void {
  localEdits = 0
}
