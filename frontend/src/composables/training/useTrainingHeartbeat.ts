import { onUnmounted, watch } from 'vue'

import { useTrainingStore } from '@/stores/training'
import { postTrainingHeartbeat } from '@/utils/trainingApi'

const HEARTBEAT_MS = 15000

export function useTrainingHeartbeat(enabled: () => boolean): void {
  const training = useTrainingStore()
  let timer: ReturnType<typeof setInterval> | null = null
  let inFlight = false

  async function tick(): Promise<void> {
    if (inFlight) return
    const snap = training.snapshot
    if (!enabled() || !snap.session_id || snap.org_id == null) return
    if (snap.state !== 'live' && snap.state !== 'paused') return
    inFlight = true
    try {
      const next = await postTrainingHeartbeat(snap.session_id, snap.org_id)
      training.applySnapshot(next)
    } catch {
      // Transient network errors retry on the next interval.
    } finally {
      inFlight = false
    }
  }

  function start(): void {
    if (timer != null) return
    void tick()
    timer = setInterval(() => {
      void tick()
    }, HEARTBEAT_MS)
  }

  function stop(): void {
    if (timer != null) {
      clearInterval(timer)
      timer = null
    }
  }

  function onShown(): void {
    if (document.visibilityState === 'visible' && enabled() && training.isActive) {
      void tick()
    }
  }

  watch(
    () => [enabled(), training.snapshot.session_id, training.snapshot.state],
    () => {
      if (enabled() && training.isActive) start()
      else stop()
    },
    { immediate: true }
  )

  document.addEventListener('visibilitychange', onShown)
  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onShown)
    stop()
  })
}
