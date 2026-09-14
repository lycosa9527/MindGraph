import { onUnmounted, watch } from 'vue'

import { useTrainingStore } from '@/stores/training'
import { postTrainingHeartbeat } from '@/utils/trainingApi'

export function useTrainingHeartbeat(enabled: () => boolean): void {
  const training = useTrainingStore()
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
      // Transient network errors retry on the next visibility or enable.
    } finally {
      inFlight = false
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
      if (enabled() && training.isActive) {
        void tick()
      }
    },
    { immediate: true }
  )

  document.addEventListener('visibilitychange', onShown)
  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onShown)
  })
}
