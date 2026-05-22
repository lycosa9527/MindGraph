/**
 * Polls ``GET /api/kitty/desktop_focus`` so mobile Kitty can align its WebSocket scope
 * with the library diagram the user has open on desktop MindGraph when local Pinia has no
 * ``activeDiagramId``.
 */
import { type Ref, onUnmounted, ref, watch } from 'vue'

import { KITTY_PAIR_POLL_MS } from './runKittyIntervalPoll'

export function useKittyDesktopFocusHint(pollEnabled: Ref<boolean>) {
  const diagramLibraryId = ref<string | null>(null)
  const updatedAt = ref<number | null>(null)
  let intervalId: ReturnType<typeof setInterval> | null = null

  async function tick(): Promise<void> {
    if (!pollEnabled.value) {
      return
    }
    try {
      const res = await fetch('/api/kitty/desktop_focus', {
        credentials: 'same-origin',
      })
      if (!res.ok) {
        diagramLibraryId.value = null
        updatedAt.value = null
        return
      }
      const data: unknown = await res.json()
      if (typeof data !== 'object' || data === null || !('diagram_library_id' in data)) {
        diagramLibraryId.value = null
        updatedAt.value = null
        return
      }
      const raw = data as unknown as Record<string, unknown>
      const lib = raw.diagram_library_id
      const ts = raw.updated_at
      diagramLibraryId.value = typeof lib === 'string' && lib.length > 0 ? lib : null
      updatedAt.value =
        typeof ts === 'number' ? ts : typeof ts === 'string' && /^\d+$/.test(ts) ? Number(ts) : null
    } catch {
      diagramLibraryId.value = null
      updatedAt.value = null
    }
  }

  function startPolling(): void {
    stopPolling()
    void tick()
    intervalId = setInterval(() => {
      void tick()
    }, KITTY_PAIR_POLL_MS)
  }

  function stopPolling(): void {
    if (intervalId != null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  watch(
    pollEnabled,
    () => {
      if (pollEnabled.value) {
        startPolling()
      } else {
        stopPolling()
      }
    },
    { immediate: true }
  )

  onUnmounted(() => {
    stopPolling()
  })

  return { diagramLibraryId, updatedAt, refresh: tick }
}
