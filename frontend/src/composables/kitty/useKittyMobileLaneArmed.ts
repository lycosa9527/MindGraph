/**
 * Polls ``GET /api/kitty/mobile_lane/{id}`` so desktop can show a pairing indicator when
 * the same library scope has an active **mobile-started** Kitty WebSocket (``client_lane: mobile``).
 */
import { type Ref, onUnmounted, ref, watch } from 'vue'

import { KITTY_PAIR_POLL_MS } from './runKittyIntervalPoll'

export function useKittyMobileLaneArmed(
  libraryDiagramId: Ref<string | null | undefined>,
  pollEnabled: Ref<boolean>
) {
  const armed = ref(false)
  let intervalId: ReturnType<typeof setInterval> | null = null

  async function tick(): Promise<void> {
    const id = libraryDiagramId.value
    if (!pollEnabled.value || id == null || id === '') {
      armed.value = false
      return
    }
    try {
      const res = await fetch(`/api/kitty/mobile_lane/${encodeURIComponent(id)}`, {
        credentials: 'same-origin',
      })
      if (!res.ok) {
        armed.value = false
        return
      }
      const data: unknown = await res.json()
      armed.value =
        typeof data === 'object' &&
        data !== null &&
        'armed' in data &&
        Boolean((data as { armed: unknown }).armed)
    } catch {
      armed.value = false
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
    [libraryDiagramId, pollEnabled],
    () => {
      if (pollEnabled.value) {
        startPolling()
      } else {
        stopPolling()
        armed.value = false
      }
    },
    { immediate: true }
  )

  onUnmounted(() => {
    stopPolling()
  })

  return { armed, refresh: tick }
}
