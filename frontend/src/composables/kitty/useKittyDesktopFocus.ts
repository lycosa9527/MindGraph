/**
 * Desktop focus discovery (mobile poll) and publish (desktop PUT) for Kitty pairing.
 */
import { type Ref, onUnmounted, ref, watch } from 'vue'

import { KITTY_PAIR_POLL_MS } from '@/composables/kitty/runKittyIntervalPoll'

const DEBOUNCE_MS = 480
/** Keep Redis focus fresh while canvas stays open (mobile freshness checks). */
const FOCUS_HEARTBEAT_MS = 60_000

async function putDesktopFocusDiagram(diagramLibraryId: string | null): Promise<void> {
  try {
    await fetch('/api/kitty/desktop_focus', {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ diagram_library_id: diagramLibraryId }),
    })
  } catch {
    /* best-effort */
  }
}

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
      const raw = data as Record<string, unknown>
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
    }
    intervalId = null
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

export function useKittyDesktopFocusPublish(options: {
  libraryDiagramId: Ref<string | null | undefined>
  enabled: Ref<boolean>
}): void {
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null

  function flush(): void {
    const idRaw = options.libraryDiagramId.value
    const id = options.enabled.value && idRaw != null && idRaw !== '' ? String(idRaw) : null
    void putDesktopFocusDiagram(id)
  }

  function schedule(): void {
    if (debounceTimer != null) {
      clearTimeout(debounceTimer)
    }
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      flush()
    }, DEBOUNCE_MS)
  }

  function stopHeartbeat(): void {
    if (heartbeatTimer != null) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function startHeartbeat(): void {
    stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      if (!options.enabled.value) {
        return
      }
      flush()
    }, FOCUS_HEARTBEAT_MS)
  }

  watch(
    () => [options.libraryDiagramId.value, options.enabled.value] as const,
    ([, enabled]) => {
      schedule()
      if (enabled) {
        startHeartbeat()
      } else {
        stopHeartbeat()
      }
    },
    { flush: 'post', immediate: true }
  )

  onUnmounted(() => {
    if (debounceTimer != null) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    stopHeartbeat()
    void putDesktopFocusDiagram(null)
  })
}
