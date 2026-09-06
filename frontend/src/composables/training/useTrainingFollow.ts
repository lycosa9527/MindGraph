/**
 * App-wide training snapshot listener (SSE doorbell + GET, poll fallback).
 */
import { onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { requestTrainingRosterInvalidate } from '@/composables/training/trainingCommands'
import { trainingActivityPageKey } from '@/composables/training/trainingFriendLine'
import { useAuthStore } from '@/stores/auth'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useTrainingStore } from '@/stores/training'
import { fetchTrainingCommand, postTrainingActivity } from '@/utils/trainingApi'
import {
  canOpenTrainingEvents,
  isTrainingRemotePath,
  shouldHoldTrainingHostOnMobile,
  shouldSkipTrainingFollow,
  trainingEventsUrl,
} from '@/utils/trainingClient'

import {
  applyTrainingNavigate,
  isMediaTrainingStep,
  shouldForceNavigate,
  trainingFreeLockDecision,
  trainingStepLocation,
} from './applyTrainingSnapshot'
import { applyTrainingUiTarget } from './applyTrainingUiTarget'

const POLL_MS = 2000
const POLL_MAX_MS = 15000
const ACTIVITY_MS = 10000

export function useTrainingFollow(): void {
  const authStore = useAuthStore()
  const flags = useFeatureFlagsStore()
  const training = useTrainingStore()
  const router = useRouter()
  const route = useRoute()

  let source: EventSource | null = null
  let sourceUrl: string | null = null
  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let activityTimer: ReturnType<typeof setInterval> | null = null
  let pollFallback = false
  let pollDelay = POLL_MS
  let pullChain: Promise<void> = Promise.resolve()
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

  function pullCommand(): Promise<void> {
    pullQueued = true
    const scheduled = pullChain.then(async () => {
      if (!pullQueued) return
      do {
        pullQueued = false
        await runPullCommand()
      } while (pullQueued)
    })
    pullChain = scheduled.then(
      () => undefined,
      () => undefined
    )
    return scheduled
  }

  function canOpenEvents(): boolean {
    return canOpenTrainingEvents(authStore.isPlatformLevel, resolveOrgId())
  }

  async function runPullCommand(): Promise<void> {
    if (!canRun() || !canOpenEvents()) return
    const orgId = resolveOrgId()
    const result = await fetchTrainingCommand(orgId, training.commandEtag)
    if (result.etag) training.setCommandEtag(result.etag)
    if (result.notModified || result.snapshot == null) return
    training.applySnapshot(result.snapshot)
    const applied = training.snapshot
    if (
      applied.session_id !== result.snapshot.session_id ||
      applied.seq !== result.snapshot.seq
    ) {
      return
    }
    if (applied.state !== 'live') {
      training.markApplied(applied.seq)
      return
    }
    if (
      shouldHoldTrainingHostOnMobile(
        route.path,
        applied.instructor_id,
        Number(authStore.user?.id) || null
      )
    ) {
      training.markApplied(applied.seq)
      return
    }
    if (shouldForceNavigate(applied, training.lastAppliedSeq)) {
      const ok = await applyTrainingNavigate(router, route.path, applied)
      const step = applied.step
      if (ok || step?.modal_key || step?.focus_key) {
        await applyTrainingUiTarget({
          modalKey: step?.modal_key,
          focusKey: step?.focus_key,
        })
      }
      if (ok || !trainingStepLocation(route.path, applied)) {
        training.markApplied(applied.seq)
      }
    } else {
      if (applied.pull_users === false) {
        await applyTrainingUiTarget({ modalKey: null, focusKey: null })
      }
      if (
        applied.state !== 'live' ||
        isMediaTrainingStep(applied) ||
        applied.pull_users === false
      ) {
        training.markApplied(applied.seq)
      }
    }
  }

  function closeSource(): void {
    if (source) {
      source.close()
      source = null
    }
    sourceUrl = null
  }

  function openSource(): void {
    if (typeof EventSource === 'undefined') {
      pollFallback = true
      return
    }
    const url = trainingEventsUrl(resolveOrgId(), authStore.isPlatformLevel)
    if (source != null && sourceUrl === url) return
    closeSource()
    const next = new EventSource(url)
    sourceUrl = url
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
    const tick = (): void => {
      if (pollFallback) {
        void pullCommand()
      }
      pollDelay = Math.min(pollDelay * 2, POLL_MAX_MS)
      pollTimer = window.setTimeout(tick, pollDelay)
    }
    pollTimer = window.setTimeout(tick, pollDelay)
  }

  function stopPolling(): void {
    if (pollTimer != null) {
      window.clearTimeout(pollTimer)
      pollTimer = null
    }
    pollDelay = POLL_MS
  }

  function startActivity(): void {
    if (activityTimer != null || !authStore.isTeacher) return
    if (isTrainingRemotePath(route.path)) return
    const send = (): void => {
      if (activityInFlight) return
      activityInFlight = true
      void postTrainingActivity({
        diagram_type: training.snapshot.diagram_type,
        page_key: trainingActivityPageKey(route.path, training.snapshot),
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
    if (!canRun() || !canOpenEvents()) {
      disconnect()
      return
    }
    const url = trainingEventsUrl(resolveOrgId(), authStore.isPlatformLevel)
    if (typeof EventSource === 'undefined') {
      pollFallback = true
    } else if (sourceUrl !== url) {
      pollFallback = false
      stopPolling()
    }
    void pullCommand()
    if (pollFallback) {
      startPolling()
    } else {
      openSource()
    }
    stopActivity()
    startActivity()
  }

  function disconnect(): void {
    closeSource()
    stopPolling()
    stopActivity()
  }

  function onVisibility(): void {
    if (document.visibilityState !== 'visible') return
    if (!canRun() || !canOpenEvents()) return
    if (pollFallback && typeof EventSource !== 'undefined') {
      pollFallback = false
      stopPolling()
      openSource()
    }
    void pullCommand()
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
    () => route.path,
    () => {
      stopActivity()
      startActivity()
    }
  )

  watch(
    () => authStore.isAuthSessionVerified,
    (ok, was) => {
      if (ok && !was) {
        closeSource()
        connect()
      }
    }
  )

  document.addEventListener('visibilitychange', onVisibility)
  const stopFreeLock = router.beforeEach((to, from) => {
    return trainingFreeLockDecision(
      training.snapshot,
      Number(authStore.user?.id) || null,
      from.path,
      to.path
    )
  })
  onUnmounted(() => {
    stopFreeLock()
    document.removeEventListener('visibilitychange', onVisibility)
    disconnect()
    training.reset()
  })
}
