/**
 * Consumes Kitty cross-device Redis queue: when mobile voice asks for a desktop canvas, desktop
 * tab polls ``GET /api/kitty/desktop_action/pop`` and navigates to ``/canvas`` with slug + seeds.
 */
import { onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import { KITTY_PAIR_POLL_MS } from '@/composables/kitty/runKittyIntervalPoll'
import type { DiagramType } from '@/types'
import { useAuthStore } from '@/stores'

const VALID = new Set<string>(VALID_DIAGRAM_TYPES)

interface OpenCanvasQueued {
  kind?: unknown
  diagram_type?: unknown
  topic?: unknown
  left?: unknown
  right?: unknown
}

function isDiagramType(slug: unknown): slug is DiagramType {
  return typeof slug === 'string' && VALID.has(slug)
}

export function useKittyDesktopActionPoll(): void {
  const authStore = useAuthStore()
  const { isAuthenticated } = storeToRefs(authStore)
  const route = useRoute()
  const router = useRouter()
  let intervalId: ReturnType<typeof setInterval> | null = null

  function surfaceIsMobileKittyLane(): boolean {
    if (route.meta.layout === 'mobile') return true
    const p = route.path
    return p === '/m' || p.startsWith('/m/')
  }

  async function tick(): Promise<void> {
    if (!isAuthenticated.value || surfaceIsMobileKittyLane()) {
      return
    }
    try {
      const res = await fetch('/api/kitty/desktop_action/pop', { credentials: 'same-origin' })
      if (!res.ok) {
        return
      }
      const envelope: unknown = await res.json()
      if (
        typeof envelope !== 'object' ||
        envelope === null ||
        !('action' in envelope) ||
        envelope.action == null ||
        typeof envelope.action !== 'object'
      ) {
        return
      }
      const act = envelope.action as OpenCanvasQueued
      if (act.kind !== 'open_canvas') {
        return
      }
      const dt = act.diagram_type
      if (!isDiagramType(dt)) {
        return
      }

      const q: Record<string, string> = { type: dt }
      const topic = typeof act.topic === 'string' ? act.topic.trim() : ''
      if (topic.length > 0) {
        q.kitty_topic = topic.slice(0, 512)
      }
      const left = typeof act.left === 'string' ? act.left.trim() : ''
      const right = typeof act.right === 'string' ? act.right.trim() : ''
      if (left.length > 0) {
        q.kitty_left = left.slice(0, 256)
      }
      if (right.length > 0) {
        q.kitty_right = right.slice(0, 256)
      }
      await router.push({ path: '/canvas', query: q }).catch(() => undefined)
    } catch {
      /* ignore transient network failures */
    }
  }

  function start(): void {
    stop()
    void tick()
    intervalId = setInterval(() => {
      void tick()
    }, KITTY_PAIR_POLL_MS)
  }

  function stop(): void {
    if (intervalId != null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  watch(
    () => [isAuthenticated.value, route.path, route.meta.layout] as const,
    ([auth]) => {
      if (auth && !surfaceIsMobileKittyLane()) {
        start()
      } else {
        stop()
      }
    },
    { immediate: true }
  )

  onUnmounted(() => {
    stop()
  })
}
