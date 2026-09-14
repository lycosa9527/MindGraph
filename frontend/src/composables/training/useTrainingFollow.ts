/**
 * App-wide training snapshot listener (SSE doorbell + GET).
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

export function useTrainingFollow(): void {
  const authStore = useAuthStore()
  const flags = useFeatureFlagsStore()
  const training = useTrainingStore()
  const router = useRouter()
  const route = useRoute()

  let source: EventSource | null = null
  let sourceUrl: string | null = null
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
    if (authStore.isPlatformLevel && resolveOrgId() == null) {
      await training.hydrateHostedSession()
      return
    }
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
      return
    }
    const url = trainingEventsUrl(resolveOrgId(), authStore.isPlatformLevel)
    if (source != null && sourceUrl === url) return
    closeSource()
    const next = new EventSource(url)
    sourceUrl = url
    let errorHydrated = false
    next.onopen = () => {
      errorHydrated = false
    }
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
      if (errorHydrated) return
      errorHydrated = true
      void pullCommand()
    }
    source = next
  }

  function sendActivity(): void {
    if (!authStore.isTeacher) return
    if (isTrainingRemotePath(route.path)) return
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

  function connect(): void {
    if (!canRun() || !canOpenEvents()) {
      disconnect()
      return
    }
    void pullCommand()
    openSource()
    sendActivity()
  }

  function disconnect(): void {
    closeSource()
  }

  function onVisibility(): void {
    if (document.visibilityState !== 'visible') return
    if (!canRun() || !canOpenEvents()) return
    if (source == null) {
      openSource()
    }
    void pullCommand()
    sendActivity()
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
      sendActivity()
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
