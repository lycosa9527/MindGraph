/**
 * Event-driven hosted-session hydrate for the phone remote and /m card.
 * Show / pageshow / mount GET; poll only while waiting so desktop Play lights up.
 */
import { onMounted, onUnmounted, watch } from 'vue'

import { useAuthStore } from '@/stores/auth'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useTrainingStore } from '@/stores/training'

import { trainingRemotePhase, trainingRemoteShouldPollHost } from './trainingRemoteView'

export const TRAINING_REMOTE_HYDRATE_MS = 2000

export function useTrainingRemoteSync(options?: { pollWhileWaiting?: boolean }): void {
  const pollWhileWaiting = options?.pollWhileWaiting !== false
  const authStore = useAuthStore()
  const flags = useFeatureFlagsStore()
  const training = useTrainingStore()
  let timer: ReturnType<typeof setInterval> | null = null
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
      // Next visibility / poll tick retries.
    } finally {
      inFlight = false
    }
  }

  function wantsPoll(): boolean {
    if (!pollWhileWaiting) return false
    const phase = trainingRemotePhase(training.snapshot, Number(authStore.user?.id) || null)
    return trainingRemoteShouldPollHost(phase, training.leadingOrgId)
  }

  function startPoll(): void {
    if (timer != null) return
    timer = setInterval(() => {
      void hydrate()
    }, TRAINING_REMOTE_HYDRATE_MS)
  }

  function stopPoll(): void {
    if (timer == null) return
    clearInterval(timer)
    timer = null
  }

  function onShown(): void {
    if (document.visibilityState !== 'visible') return
    void hydrate()
  }

  watch(wantsPoll, (should) => {
    if (should) startPoll()
    else stopPoll()
  }, { immediate: true })

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
    stopPoll()
  })
}