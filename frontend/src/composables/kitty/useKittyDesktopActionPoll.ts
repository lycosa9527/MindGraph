/**
 * Consumes Kitty cross-device Redis queue when mobile Kitty is active: SSE wake on
 * ``GET /api/kitty/desktop_wake/stream``, fallback watch on ``desktop_pairing?wait_sec=0``,
 * then long-poll chains ``desktop_pairing?wait_sec=25`` and navigates on ``open_canvas``.
 */
import { onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import { createKittyDesktopPollLeader } from '@/composables/kitty/kittyDesktopPollLeader'
import {
  createKittyDesktopWakeStream,
  type KittyDesktopWakeMobileActive,
} from '@/composables/kitty/createKittyDesktopWakeStream'
import {
  publishKittyMobileActiveHub,
} from '@/composables/kitty/kittyDesktopMobileActiveHub'
import {
  KITTY_DESKTOP_PAIR_WAIT_SEC,
  KITTY_MOBILE_WATCH_MS,
} from '@/composables/kitty/runKittyIntervalPoll'
import type { DiagramType } from '@/types'
import { useAuthStore, useFeatureFlagsStore } from '@/stores'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'

const VALID = new Set<string>(VALID_DIAGRAM_TYPES)

type PollPhase = 'off' | 'watching' | 'consuming'

interface OpenCanvasQueued {
  kind?: unknown
  diagram_type?: unknown
  topic?: unknown
  left?: unknown
  right?: unknown
}

interface DesktopPairingResponse {
  active?: unknown
  action?: unknown
  scopes?: unknown
  primary_scope?: unknown
}

function isDiagramType(slug: unknown): slug is DiagramType {
  return typeof slug === 'string' && VALID.has(slug)
}

function pairingUrl(waitSec: number): string {
  const params = new URLSearchParams()
  params.set('wait_sec', String(waitSec))
  return `/api/kitty/desktop_pairing?${params.toString()}`
}

export function useKittyDesktopActionPoll(): void {
  const authStore = useAuthStore()
  const featureFlagsStore = useFeatureFlagsStore()
  const { isAuthenticated } = storeToRefs(authStore)
  const route = useRoute()
  const router = useRouter()

  let phase: PollPhase = 'off'
  let intervalId: ReturnType<typeof setInterval> | null = null
  let consumeRunId = 0
  let flagsLoaded = false
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

  function pollingAllowed(): boolean {
    return (
      flagsLoaded &&
      isPollLeader &&
      kittyFeatureEnabled() &&
      isAuthenticated.value &&
      !surfaceIsMobileKittyLane() &&
      !isHeadlessExportSurface() &&
      !document.hidden
    )
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

  async function handleOpenCanvasAction(action: unknown): Promise<void> {
    if (action == null || typeof action !== 'object') {
      return
    }
    const act = action as OpenCanvasQueued
    if (act.kind !== 'open_canvas') {
      return
    }
    const dt = act.diagram_type
    if (!isDiagramType(dt)) {
      return
    }

    const q: Record<string, string> = { type: dt }
    const topic = typeof act.topic === 'string' ? act.topic.trim() : ''
    if (topic.length > 0) {
      q.kitty_topic = topic.slice(0, 512)
    }
    const left = typeof act.left === 'string' ? act.left.trim() : ''
    const right = typeof act.right === 'string' ? act.right.trim() : ''
    if (left.length > 0) {
      q.kitty_left = left.slice(0, 256)
    }
    if (right.length > 0) {
      q.kitty_right = right.slice(0, 256)
    }
    await router.push({ path: '/canvas', query: q }).catch(() => undefined)
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
    stopWakeStreamConnection()
    if (!pollingAllowed()) {
      return
    }
    stopWakeStream = createKittyDesktopWakeStream({
      onMobileActive: handleWakeMobileActive,
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
          await handleOpenCanvasAction(data.action)
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
    if (!pollingAllowed()) {
      stop()
      return
    }
    if (phase === 'consuming') {
      return
    }
    if (phase === 'watching' && intervalId != null) {
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
    stopPollLeader = createKittyDesktopPollLeader((leader) => {
      isPollLeader = leader
      syncPolling()
    })
    void featureFlagsStore.fetchFlags().finally(() => {
      flagsLoaded = true
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
        flagsLoaded,
      ] as const,
    () => {
      syncPolling()
    },
    { immediate: true }
  )

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    if (stopPollLeader != null) {
      stopPollLeader()
      stopPollLeader = null
    }
    stop()
  })
}
