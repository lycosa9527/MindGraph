/**
 * Consumes Kitty cross-device Redis queue when mobile Kitty is active: SSE wake on
 * ``GET /api/kitty/desktop_wake/stream``, fallback watch on ``desktop_pairing?wait_sec=0``,
 * then long-poll chains ``desktop_pairing?wait_sec=25`` and navigates on ``open_canvas``.
 */
import { onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import {
  type KittyDesktopWakeMobileActive,
  createKittyDesktopWakeStream,
} from '@/composables/kitty/createKittyDesktopWakeStream'
import { handleKittyDesktopQueuedAction } from '@/composables/kitty/kittyDesktopActionHandlers'
import { publishKittyMobileActiveHub } from '@/composables/kitty/kittyDesktopMobileActiveHub'
import { createKittyDesktopPollLeader } from '@/composables/kitty/kittyDesktopPollLeader'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import {
  KITTY_DESKTOP_PAIR_WAIT_SEC,
  KITTY_MOBILE_WATCH_MS,
} from '@/composables/kitty/runKittyIntervalPoll'
import { useAuthStore, useFeatureFlagsStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'

type PollPhase = 'off' | 'watching' | 'consuming'

interface DesktopPairingResponse {
  active?: unknown
  action?: unknown
  scopes?: unknown
  primary_scope?: unknown
}

function pairingUrl(waitSec: number): string {
  const params = new URLSearchParams()
  params.set('wait_sec', String(waitSec))
  return `/api/kitty/desktop_pairing?${params.toString()}`
}

export function useKittyDesktopActionPoll(): void {
  const authStore = useAuthStore()
  const featureFlagsStore = useFeatureFlagsStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const { isAuthenticated } = storeToRefs(authStore)
  const { t } = useLanguage()
  const route = useRoute()
  const router = useRouter()

  let phase: PollPhase = 'off'
  let intervalId: ReturnType<typeof setInterval> | null = null
  let consumeRunId = 0
  let isPollLeader = false
  let stopPollLeader: (() => void) | null = null
  let stopWakeStream: (() => void) | null = null
  let wakeStreamConnected = false
  let pairingAbort: AbortController | null = null
  let watchTickInFlight = false

  function surfaceIsMobileKittyLane(): boolean {
    if (route.meta.layout === 'mobile') return true
    const p = route.path
    return p === '/m' || p.startsWith('/m/')
  }

  function isHeadlessExportSurface(): boolean {
    return route.path === '/export-render' || isMindgraphHeadlessExportSession()
  }

  function kittyFeatureEnabled(): boolean {
    return featureFlagsStore.getFeatureKittyAgent()
  }

  function flagsReady(): boolean {
    return featureFlagsStore.flags != null
  }

  /** Elect a desktop poll leader only when this surface could actually poll. */
  function pollLeaderEligible(): boolean {
    return (
      flagsReady() &&
      kittyFeatureEnabled() &&
      isAuthenticated.value &&
      !surfaceIsMobileKittyLane() &&
      !isHeadlessExportSurface()
    )
  }

  function pollingAllowed(): boolean {
    return pollLeaderEligible() && isPollLeader && !document.hidden
  }

  function ensurePollLeader(): void {
    if (!pollLeaderEligible()) {
      tearDownPollLeader()
      return
    }
    if (stopPollLeader != null) {
      return
    }
    stopPollLeader = createKittyDesktopPollLeader((leader) => {
      isPollLeader = leader
      syncPolling()
    })
  }

  function tearDownPollLeader(): void {
    if (stopPollLeader == null) {
      isPollLeader = false
      return
    }
    stopPollLeader()
    stopPollLeader = null
    isPollLeader = false
  }

  function clearIntervalId(): void {
    if (intervalId != null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  function setPhase(next: PollPhase): void {
    phase = next
  }

  function cancelConsumeLoop(): void {
    consumeRunId += 1
  }

  function abortPairingFetch(): void {
    if (pairingAbort != null) {
      pairingAbort.abort()
      pairingAbort = null
    }
  }

  async function fetchDesktopPairing(waitSec: number): Promise<DesktopPairingResponse | null> {
    abortPairingFetch()
    pairingAbort = new AbortController()
    const signal = pairingAbort.signal
    try {
      const res = await fetch(pairingUrl(waitSec), {
        credentials: 'same-origin',
        signal,
      })
      if (!res.ok) {
        return null
      }
      return (await res.json()) as DesktopPairingResponse
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return null
      }
      if (error instanceof Error && error.name === 'AbortError') {
        return null
      }
      return null
    } finally {
      if (pairingAbort?.signal === signal) {
        pairingAbort = null
      }
    }
  }

  function stopWakeStreamConnection(): void {
    if (stopWakeStream != null) {
      stopWakeStream()
      stopWakeStream = null
    }
    wakeStreamConnected = false
  }

  async function drainPendingDesktopAction(): Promise<void> {
    if (!pollingAllowed()) {
      return
    }
    try {
      const data = await fetchDesktopPairing(0)
      if (data?.action != null) {
        await handleKittyDesktopQueuedAction(data.action, {
          routePath: route.path,
          savedDiagramsStore,
          router,
          route,
          t,
        })
      }
    } catch {
      /* ignore transient network failures */
    }
  }

  function handleWakeMobileActive(payload: KittyDesktopWakeMobileActive): void {
    publishKittyMobileActiveHub(payload)
    if (!pollingAllowed()) {
      return
    }
    if (payload.active === true) {
      if (phase !== 'consuming') {
        startConsuming()
      }
      return
    }
    if (phase === 'consuming') {
      startWatching()
    }
  }

  function startWakeStreamConnection(): void {
    if (stopWakeStream != null && wakeStreamConnected) {
      return
    }
    stopWakeStreamConnection()
    if (!pollingAllowed()) {
      return
    }
    stopWakeStream = createKittyDesktopWakeStream({
      onMobileActive: handleWakeMobileActive,
      onDesktopActionPending: () => {
        void drainPendingDesktopAction()
      },
      onDiagramUpdate: (payload) => {
        const scope = typeof payload.scope === 'string' ? payload.scope : undefined
        const action = typeof payload.action === 'string' ? payload.action : undefined
        traceKittyWorkflow('hub', 'sse_diagram', String(action ?? 'diagram_update'), {
          scope,
          action,
        })
        eventBus.emit('kitty:desktop_diagram_update', {
          scope,
          action,
          updates: payload.updates,
          mutation_id:
            typeof payload.mutation_id === 'string' ? payload.mutation_id : undefined,
        })
      },
      onSelectionUpdate: (payload) => {
        const scope = typeof payload.scope === 'string' ? payload.scope : undefined
        const raw = payload.selected_nodes
        const selected_nodes = Array.isArray(raw)
          ? raw.filter((item): item is string => typeof item === 'string')
          : []
        traceKittyWorkflow('hub', 'sse_selection', `${selected_nodes.length} node(s)`, { scope })
        eventBus.emit('kitty:desktop_selection_update', {
          scope,
          selected_nodes,
        })
      },
      onVoiceCommand: (payload) => {
        const scope = typeof payload.scope === 'string' ? payload.scope : undefined
        const action = typeof payload.action === 'string' ? payload.action : undefined
        const detail = typeof payload.detail === 'string' ? payload.detail : undefined
        traceKittyWorkflow('hub', 'sse_voice_cmd', detail ?? String(action ?? ''), {
          scope,
          action,
        })
        eventBus.emit('kitty:desktop_voice_command', {
          scope,
          action,
          detail,
        })
      },
      onOpen: () => {
        wakeStreamConnected = true
      },
      onClose: () => {
        wakeStreamConnected = false
      },
    })
  }

  async function tickWatch(): Promise<void> {
    if (!pollingAllowed()) {
      stop()
      return
    }
    if (wakeStreamConnected || watchTickInFlight) {
      return
    }
    watchTickInFlight = true
    try {
      const data = await fetchDesktopPairing(0)
      if (!pollingAllowed()) {
        return
      }
      if (data?.active === true) {
        publishKittyMobileActiveHub({
          type: 'mobile_active',
          active: true,
          scopes: data.scopes,
          primary_scope: data.primary_scope,
        })
        startConsuming()
        return
      }
      if (data?.action != null) {
        await handleKittyDesktopQueuedAction(data.action, {
          routePath: route.path,
          savedDiagramsStore,
          router,
          route,
          t,
        })
      }
      publishKittyMobileActiveHub({
        type: 'mobile_active',
        active: false,
        scopes: [],
        primary_scope: null,
      })
    } catch {
      /* ignore transient network failures */
    } finally {
      watchTickInFlight = false
    }
  }

  async function runConsumeLoop(runId: number): Promise<void> {
    while (runId === consumeRunId && phase === 'consuming') {
      if (!pollingAllowed()) {
        return
      }
      try {
        const data = await fetchDesktopPairing(KITTY_DESKTOP_PAIR_WAIT_SEC)
        if (runId !== consumeRunId) {
          return
        }
        if (data?.action != null) {
          await handleKittyDesktopQueuedAction(data.action, {
            routePath: route.path,
            savedDiagramsStore,
            router,
            route,
            t,
          })
        }
        if (runId !== consumeRunId || !pollingAllowed() || phase !== 'consuming') {
          return
        }
        if (data == null) {
          continue
        }
        if (data.active !== true) {
          startWatching()
          return
        }
      } catch {
        if (runId !== consumeRunId) {
          return
        }
        await new Promise((resolve) => {
          setTimeout(resolve, 1000)
        })
      }
    }
  }

  function startWatching(): void {
    cancelConsumeLoop()
    clearIntervalId()
    setPhase('watching')
    startWakeStreamConnection()
    void tickWatch()
    intervalId = setInterval(() => {
      if (!wakeStreamConnected) {
        void tickWatch()
      }
    }, KITTY_MOBILE_WATCH_MS)
  }

  function startConsuming(): void {
    cancelConsumeLoop()
    clearIntervalId()
    setPhase('consuming')
    const runId = consumeRunId
    void runConsumeLoop(runId)
  }

  function stop(): void {
    cancelConsumeLoop()
    clearIntervalId()
    abortPairingFetch()
    stopWakeStreamConnection()
    setPhase('off')
  }

  function syncPolling(): void {
    ensurePollLeader()
    if (!pollingAllowed()) {
      stop()
      return
    }
    if (phase === 'consuming') {
      return
    }
    if (phase === 'watching' && intervalId != null && stopWakeStream != null) {
      return
    }
    startWatching()
  }

  function onVisibilityChange(): void {
    if (document.hidden) {
      stop()
      return
    }
    syncPolling()
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', onVisibilityChange)
    const flagsPromise =
      featureFlagsStore.flags != null
        ? Promise.resolve()
        : featureFlagsStore.fetchFlags()
    void flagsPromise.finally(() => {
      syncPolling()
    })
  })

  watch(
    () =>
      [
        isAuthenticated.value,
        route.path,
        route.meta.layout,
        featureFlagsStore.flags?.feature_kitty_agent,
        featureFlagsStore.flags,
      ] as const,
    () => {
      syncPolling()
    },
    { immediate: true }
  )

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    tearDownPollLeader()
    stop()
  })
}
