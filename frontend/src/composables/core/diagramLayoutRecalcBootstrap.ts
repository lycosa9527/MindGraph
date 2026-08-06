/**
 * Registers diagram layout recalc listener (deferred from main.ts to first diagram mount).
 * Bumps every mounted diagram session so Showcase previews are not ignored / do not
 * only poke the editor Pinia store.
 *
 * If a bump arrives before any canvas mounts (markdown pipeline preload), the count is
 * applied when each session registers so late mounts still remeasure.
 */
import { eventBus } from '@/composables/core/useEventBus'

type LayoutRecalcSession = {
  layoutRecalcTrigger: number
}

const mountedSessions = new Set<LayoutRecalcSession>()
let pendingBumps = 0
let registered = false

function ensureBusRegistered(): void {
  if (registered) return
  registered = true
  eventBus.on('diagram:layout_recalc_bump', () => {
    if (mountedSessions.size === 0) {
      pendingBumps += 1
      return
    }
    for (const session of mountedSessions) {
      session.layoutRecalcTrigger += 1
    }
  })
}

/** Register a mounted canvas session; returns disposer for onBeforeUnmount. */
export function registerDiagramLayoutRecalcSession(session: LayoutRecalcSession): () => void {
  ensureBusRegistered()
  if (pendingBumps > 0) {
    session.layoutRecalcTrigger += pendingBumps
  }
  mountedSessions.add(session)
  return () => {
    mountedSessions.delete(session)
  }
}

/** Ensure the bus listener exists (markdown pipeline may run before any canvas). */
export function registerDiagramLayoutRecalcBootstrap(): void {
  ensureBusRegistered()
}
