/**
 * Event-driven hosted-session hydrate for the phone remote and /m card.
 * GET on mount, pageshow, and visibility. Start wakes via user-level SSE.
 */
import { onMounted, onUnmounted, watch } from 'vue'

import { useAuthStore } from '@/stores/auth'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useTrainingStore } from '@/stores/training'

export function useTrainingRemoteSync(): void {
  const authStore = useAuthStore()
  const flags = useFeatureFlagsStore()
  const training = useTrainingStore()
  let inFlight = false

  function mayHydrate(): boolean {
    if (!authStore.isAuthenticated || !authStore.isAuthSessionVerified) return false
    if (!authStore.isPlatformLevel || !flags.getFeatureTraining()) return false
    return document.visibilityState !== 'hidden'
  }

  async function hydrate(): Promise<void> {
    if (inFlight || !mayHydrate()) return
    inFlight = true
    try {
      await training.hydrateHostedSession()
    } catch {
      // Next visibility or SSE doorbell retries.
    } finally {
      inFlight = false
    }
  }

  function onShown(): void {
    if (document.visibilityState !== 'visible') return
    void hydrate()
  }

  watch(
    () => [
      authStore.isAuthenticated,
      authStore.isAuthSessionVerified,
      authStore.isPlatformLevel,
      flags.flags?.feature_training,
    ],
    () => {
      void hydrate()
    }
  )

  document.addEventListener('visibilitychange', onShown)
  window.addEventListener('pageshow', onShown)
  onMounted(() => {
    void hydrate()
  })
  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onShown)
    window.removeEventListener('pageshow', onShown)
  })
}
