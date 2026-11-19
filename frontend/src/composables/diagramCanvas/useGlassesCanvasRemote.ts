/**
 * Apply MindGlass canvas-remote nudges while a diagram is open.
 * The glasses stream wakes this page; it drains the queue once per nudge.
 */
import { onUnmounted } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { apiRequest } from '@/utils/apiClient'

import { type GlassesViewport, nextGlassesViewport } from './glassesCanvasRemote'

const NUDGE_MS = 180
const OWNER = 'GlassesCanvasRemote'

type GlassesRemoteHost = {
  getViewport: () => GlassesViewport
  setViewport: (viewport: GlassesViewport, opts?: { duration?: number }) => void
  fit: () => void
}

export function useGlassesCanvasRemote(host: GlassesRemoteHost): void {
  let pulling = false
  let pullAgain = false

  async function pull(): Promise<void> {
    if (pulling) {
      pullAgain = true
      return
    }
    pulling = true
    try {
      do {
        pullAgain = false
        const response = await apiRequest('/api/learning-space/glasses/remote')
        if (response.status === 401 || response.status === 403) return
        if (!response.ok) return
        const body = (await response.json()) as { actions?: unknown }
        const actions = Array.isArray(body.actions) ? body.actions : []
        for (const action of actions) {
          if (typeof action !== 'string') continue
          const next = nextGlassesViewport(host.getViewport(), action)
          if (next === 'fit') host.fit()
          else if (next) host.setViewport(next, { duration: NUDGE_MS })
        }
      } while (pullAgain)
    } catch {
      // A missed nudge stays queued until the next event.
    } finally {
      pulling = false
    }
  }

  eventBus.onWithOwner(
    'glasses:nudge',
    () => {
      void pull()
    },
    OWNER
  )
  void pull()

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(OWNER)
  })
}
