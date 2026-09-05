/**
 * App-wide training snapshot listener (SSE doorbell + GET, poll fallback).
 */
import { onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { requestTrainingRosterInvalidate } from '@/composables/training/trainingCommands'
import { useAuthStore } from '@/stores/auth'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useTrainingStore } from '@/stores/training'
import { fetchTrainingCommand, postTrainingActivity } from '@/utils/trainingApi'
import { shouldSkipTrainingFollow, trainingEventsUrl } from '@/utils/trainingClient'

import {
  applyTrainingNavigate,
  isMediaTrainingStep,
  shouldForceNavigate,
} from './applyTrainingSnapshot'
import { applyTrainingUiTarget } from './applyTrainingUiTarget'

const POLL_MS = 2000
const ACTIVITY_MS = 10000

export function useTrainingFollow(): void {
  const authStore = useAuthStore()
  const flags = useFeatureFlagsStore()
  const training = useTrainingStore()
  const router = useRouter()
  const route = useRoute()

  let source: EventSource | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let activityTimer: ReturnType<typeof setInterval> | null = null
  let pollFallback = false
  let pullInFlight: Promise<void> | null = null
  let pullQueued = false
  let activityInFlight = false

  function canRun(): boolean {
    if (shouldSkipTrainingFollow()) return false
    if (!flags.getFeatureTraining()) return false
    if (!authStore.isAuthenticated || !authStore.isAuthSessionVerified) return false
    return !authStore.isC2CConsumer
  }

  function resolveOrgId(): number | null {
    if (training.leadingOrgId != null) return training.leadingOrgId
    if (training.snapshot.org_id != null) return training.snapshot.org_id
    const school = authStore.user?.schoolId
    if (!school) return null
    const parsed = parseInt(school, 10)
    return Number.isNaN(parsed) ? null : parsed
  }

  async function pullCommand(): Promise<void> {
    if (pullInFlight) {
      pullQueued = true
      await pullInFlight
      return
    }
    do {
      pullQueued = false
      pullInFlight = runPullCommand()
      try {
        await pullInFlight
      } finally {
        pullInFlight = null
      }
    } while (pullQueued)
  }

  async function runPullCommand(): Promise<void> {
    if (!canRun()) return
    const orgId = resolveOrgId()
    const result = await fetchTrainingCommand(orgId, training.commandEtag)
    if (result.etag) training.setCommandEtag(result.etag)
    if (result.notModified || result.snapshot == null) return
    const previousSeq = training.lastAppliedSeq
    training.applySnapshot(result.snapshot)
    if (shouldForceNavigate(result.snapshot, previousSeq)) {
      const ok = await applyTrainingNavigate(router, route.path, result.snapshot)
      const step = result.snapshot.step
      if (ok || step?.modal_key || step?.focus_key) {
        await applyTrainingUiTarget({
          modalKey: step?.modal_key,
          focusKey: step?.focus_key,
        })
        training.markApplied(result.snapshot.seq)
      }
    } else if (result.snapshot.state !== 'live' || isMediaTrainingStep(result.snapshot)) {
      training.markApplied(result.snapshot.seq)
    }
  }

  function closeSource(): void {
    if (source) {
      source.close()
      source = null
    }
  }

  function openSource(): void {
    closeSource()
    if (typeof EventSource === 'undefined') {
      pollFallback = true
      return
    }
    const orgId = resolveOrgId()
    const next = new EventSource(trainingEventsUrl(orgId, authStore.isPlatformLevel))
    next.addEventListener('seq', () => {
      void pullCommand()
    })
    next.addEventListener('ended', () => {
      void pullCommand()
    })
    next.addEventListener('activity', () => {
      training.bumpActivity()
      requestTrainingRosterInvalidate()
    })
    next.onerror = () => {
      pollFallback = true
      closeSource()
      startPolling()
    }
    source = next
  }

  function startPolling(): void {
    if (pollTimer != null) return
    pollTimer = setInterval(() => {
      if (pollFallback) {
        void pullCommand()
      }
    }, POLL_MS)
  }

  function stopPolling(): void {
    if (pollTimer != null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function startActivity(): void {
    if (activityTimer != null || !authStore.isTeacher) return
    const send = (): void => {
      if (activityInFlight) return
      activityInFlight = true
      void postTrainingActivity({
        diagram_type: training.snapshot.diagram_type,
        generate_state: 'idle',
      }).finally(() => {
        activityInFlight = false
      })
    }
    send()
    activityTimer = setInterval(send, ACTIVITY_MS)
  }

  function stopActivity(): void {
    if (activityTimer != null) {
      clearInterval(activityTimer)
      activityTimer = null
    }
  }

  function connect(): void {
    if (!canRun()) {
      disconnect()
      return
    }
    pollFallback = typeof EventSource === 'undefined'
    void pullCommand()
    if (pollFallback) {
      startPolling()
    } else {
      openSource()
    }
    startActivity()
  }

  function disconnect(): void {
    closeSource()
    stopPolling()
    stopActivity()
  }

  function onVisibility(): void {
    if (document.visibilityState === 'visible') {
      void pullCommand()
    }
  }

  watch(
    () => [
      authStore.isAuthenticated,
      authStore.isAuthSessionVerified,
      flags.flags?.feature_training,
      training.leadingOrgId,
    ],
    () => connect(),
    { immediate: true }
  )

  watch(
    () => authStore.isAuthSessionVerified,
    (ok, was) => {
      if (ok && !was) {
        closeSource()
        if (canRun() && !pollFallback) openSource()
      }
    }
  )

  document.addEventListener('visibilitychange', onVisibility)
  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onVisibility)
    disconnect()
    training.reset()
  })
}
