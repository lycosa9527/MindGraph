import { onUnmounted, watch } from 'vue'

import { useTrainingStore } from '@/stores/training'
import { postTrainingHeartbeat } from '@/utils/trainingApi'

const HEARTBEAT_MS = 15000

export function useTrainingHeartbeat(enabled: () => boolean): void {
  const training = useTrainingStore()
  let timer: ReturnType<typeof setInterval> | null = null

  async function tick(): Promise<void> {
    const snap = training.snapshot
    if (!enabled() || !snap.session_id || snap.org_id == null) return
    if (snap.state !== 'live' && snap.state !== 'paused') return
    await postTrainingHeartbeat(snap.session_id, snap.org_id)
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

  watch(
    () => [enabled(), training.snapshot.session_id, training.snapshot.state],
    () => {
      if (enabled() && training.isActive) start()
      else stop()
    },
    { immediate: true }
  )

  onUnmounted(stop)
}
