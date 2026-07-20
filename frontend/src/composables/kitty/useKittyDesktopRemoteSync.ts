/**
 * Desktop Kitty remote sync: incremental diagram_update + selection fanout / live_context poll.
 */
import { type ComputedRef, type Ref, onUnmounted, ref, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import {
  applyKittyDiagramUpdate,
  executeKittyAgentAction,
} from '@/composables/kitty/kittyAgentActions'
import { formatKittyDiagramUpdateDebug } from '@/composables/kitty/kittyAgentDebug'
import {
  acquireKittyMobileActiveHub,
  isKittyMobileActiveHubFresh,
  useKittyMobileActiveHubSnapshot,
} from '@/composables/kitty/kittyDesktopMobileActiveHub'
import {
  getKittyDiagramContentFingerprint,
  getKittyVoiceDiagramFingerprint,
} from '@/composables/kitty/kittyDiagramFingerprint'
import { applyKittyRemoteLlmModel } from '@/composables/kitty/applyKittyRemoteLlmModel'
import { applyKittyRemoteCanvasSelection } from '@/composables/kitty/kittySelectionApply'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import {
  KITTY_LIVE_CONTEXT_POLL_MS,
} from '@/composables/kitty/runKittyIntervalPoll'
import type { KittyAgentContext } from '@/composables/kitty/kittyAgentTypes'
import { syncDiagramStoreFromVoiceContext } from '@/composables/kitty/syncDiagramStoreFromVoiceContext'
import { useDiagramStore } from '@/stores/diagram'
import { useKittySessionStore } from '@/stores/kittySession'
import { VALID_DIAGRAM_TYPES } from '@/stores/diagram/constants'
import type { DiagramType } from '@/types'

function canonicalDiagramKind(t: DiagramType | null): string {
  if (!t) {
    return ''
  }
  return t === 'mind_map' || t === 'mindmap' ? 'mindmap' : t
}

function diagramTypeFromLivePayload(raw: unknown): DiagramType | null {
  if (typeof raw !== 'string' || !raw.trim()) {
    return null
  }
  const candidate = (raw.trim() === 'mind_map' ? 'mindmap' : raw.trim()) as DiagramType
  if (!VALID_DIAGRAM_TYPES.includes(candidate)) {
    return null
  }
  return candidate
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

export function useKittyDesktopRemoteSync(options: {
  libraryDiagramId: Ref<string | null> | ComputedRef<string | null>
  syncEnabled: ComputedRef<boolean>
  collabSessionActive: ComputedRef<boolean>
  /** Canvas-owner hub persist for verified SSE apply (parity with WS inbound). */
  hubPersist?: {
    buildContext: () => KittyAgentContext
    updateContext: (ctx: KittyAgentContext) => void | Promise<void>
  }
}): { refresh: () => Promise<void> } {
  const diagramStore = useDiagramStore()
  const mobileActiveHub = useKittyMobileActiveHubSnapshot()
  const lastAppliedUpdatedAt = ref<number | null>(null)
  const lastDiagramSseAt = ref(0)
  let pollTickCount = 0
  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let pollingActive = false
  let tickInFlight = false
  let visibilityBound = false
  let releaseHub: (() => void) | null = null

  function scopeMatches(scope: string): boolean {
    const currentId = options.libraryDiagramId.value?.trim() ?? ''
    return scope.length > 0 && currentId.length > 0 && scope === currentId
  }

  function collabBlocksDiagramEdits(): boolean {
    return options.collabSessionActive.value && diagramStore.type !== 'concept_map'
  }

  function handleDiagramFanout(data: {
    scope?: unknown
    action?: unknown
    updates?: unknown
    mutation_id?: unknown
    expected_effect?: unknown
    before_fingerprint?: unknown
  }): void {
    if (!options.syncEnabled.value) {
      return
    }
    const scope = typeof data.scope === 'string' ? data.scope.trim() : ''
    if (!scopeMatches(scope)) {
      return
    }
    const action = typeof data.action === 'string' ? data.action : ''
    if (!action) {
      return
    }
    const mutationId =
      typeof data.mutation_id === 'string' && data.mutation_id.trim() !== ''
        ? data.mutation_id.trim()
        : ''
    const kittySession = useKittySessionStore()

    // Verified edits: Redis SSE is the cross-worker apply path when owner WS
    // is on another Uvicorn process. Observers must not re-apply.
    // Collab must not drop here — mutation bus nacks with collab_active so the
    // pending server future completes (avoids ack_timeout).
    if (mutationId !== '') {
      if (!kittySession.ownsKittySession) {
        return
      }
      lastDiagramSseAt.value = Date.now()
      const updates = isRecord(data.updates) || Array.isArray(data.updates) ? data.updates : {}
      const summary = formatKittyDiagramUpdateDebug(action, updates as Record<string, unknown>)
      traceKittyWorkflow('desktop', 'canvas_apply_verified_sse', summary, { scope, action })
      eventBus.emit('kitty:diagram_mutation_requested', {
        action,
        updates: updates as Record<string, unknown>,
        mutationId,
        expectedEffect:
          data.expected_effect && typeof data.expected_effect === 'object'
            ? (data.expected_effect as import('@/utils/diagramEditVerify').DiagramEditExpectedEffect)
            : undefined,
        beforeFingerprint:
          data.before_fingerprint &&
          typeof data.before_fingerprint === 'object' &&
          Array.isArray((data.before_fingerprint as { nodes?: unknown }).nodes) &&
          Array.isArray((data.before_fingerprint as { connections?: unknown }).connections)
            ? {
                nodes: (data.before_fingerprint as { nodes: import('@/types').DiagramNode[] })
                  .nodes,
                connections: (
                  data.before_fingerprint as { connections: import('@/types').Connection[] }
                ).connections,
              }
            : undefined,
        sendAck: kittySession.getMutationAckSender() ?? undefined,
        hubPersist: options.hubPersist
          ? {
              buildContext: options.hubPersist.buildContext,
              updateContext: options.hubPersist.updateContext,
              scope: scope || options.libraryDiagramId.value?.trim() || null,
            }
          : undefined,
        lane: 'desktop',
      })
      return
    }

    if (collabBlocksDiagramEdits()) {
      return
    }

    // Owning tab already applied via Kitty WS / Pinia; observers use live_context recovery.
    if (kittySession.ownsKittySession) {
      return
    }
    lastDiagramSseAt.value = Date.now()
    const updates = isRecord(data.updates) || Array.isArray(data.updates) ? data.updates : {}
    const summary = formatKittyDiagramUpdateDebug(action, updates as Record<string, unknown>)
    traceKittyWorkflow('desktop', 'canvas_apply', summary, { scope, action })
    applyKittyDiagramUpdate(action, updates as Record<string, unknown>)
  }

  function handleCanvasActionFanout(data: {
    scope?: string
    action?: string
    params?: Record<string, unknown>
  }): void {
    if (!options.syncEnabled.value || collabBlocksDiagramEdits()) {
      return
    }
    const kittySession = useKittySessionStore()
    if (!kittySession.ownsKittySession) {
      return
    }
    const scope = typeof data.scope === 'string' ? data.scope.trim() : ''
    if (!scopeMatches(scope)) {
      return
    }
    const action = typeof data.action === 'string' ? data.action.trim() : ''
    if (!action) {
      return
    }
    traceKittyWorkflow('desktop', 'canvas_action_sse', action, { scope, action })
    executeKittyAgentAction(action, data.params ?? {})
  }

  function handleSelectionFanout(data: { scope?: string; selected_nodes?: string[] }): void {
    if (!options.syncEnabled.value || options.collabSessionActive.value) {
      return
    }
    const scope = typeof data.scope === 'string' ? data.scope.trim() : ''
    if (!scopeMatches(scope)) {
      return
    }
    applyKittyRemoteCanvasSelection(data.selected_nodes ?? [], { canvasHighlight: true })
    traceKittyWorkflow(
      'desktop',
      'selection_apply',
      `${(data.selected_nodes ?? []).length} node(s)`,
      { scope }
    )
  }

  function handleLlmModelFanout(data: {
    scope?: string
    selected_llm_model?: string | null
  }): void {
    if (!options.syncEnabled.value || options.collabSessionActive.value) {
      return
    }
    const scope = typeof data.scope === 'string' ? data.scope.trim() : ''
    if (!scopeMatches(scope)) {
      return
    }
    void applyKittyRemoteLlmModel(data.selected_llm_model).then((changed) => {
      if (!changed) {
        return
      }
      traceKittyWorkflow(
        'desktop',
        'llm_model_apply',
        data.selected_llm_model == null || data.selected_llm_model === ''
          ? 'cleared'
          : String(data.selected_llm_model),
        { scope }
      )
    })
  }

  async function tryRecoverDiagramFromLiveContext(
    data: {
      updated_at?: number
      diagram_type?: string
      diagram_data?: unknown
      selected_nodes?: unknown
    },
    forceRecovery: boolean
  ): Promise<void> {
    const ua = data.updated_at
    if (typeof ua !== 'number') {
      return
    }
    const appliedUpdatedAt: number = ua
    if (
      lastAppliedUpdatedAt.value !== null &&
      appliedUpdatedAt <= lastAppliedUpdatedAt.value
    ) {
      return
    }
    const dt = diagramTypeFromLivePayload(data.diagram_type)
    const storeType = diagramStore.type
    if (dt == null || storeType == null) {
      return
    }
    if (canonicalDiagramKind(dt) !== canonicalDiagramKind(storeType)) {
      return
    }

    const diagramData = isRecord(data.diagram_data) ? data.diagram_data : null
    const localNodes = diagramStore.data?.nodes ?? []
    const hubNodes =
      diagramData != null && Array.isArray(diagramData.nodes) ? diagramData.nodes : []
    const hubHasCanonicalNodes = hubNodes.length > 0
    const kittySession = useKittySessionStore()

    function applyLiveMetaOnly(reason: string): void {
      if (
        Array.isArray(data.selected_nodes) &&
        data.selected_nodes.every((x) => typeof x === 'string')
      ) {
        applyKittyRemoteCanvasSelection(data.selected_nodes as string[], {
          canvasHighlight: true,
        })
      }
      if ('selected_llm_model' in data) {
        void applyKittyRemoteLlmModel(data.selected_llm_model)
      }
      lastAppliedUpdatedAt.value = appliedUpdatedAt
      traceKittyWorkflow('desktop', 'live_context_skip', reason, {
        scope: options.libraryDiagramId.value?.trim(),
      })
    }

    // Owning tab Pinia is SoT (verified apply + autocomplete paste). Reloading
    // Redis live_context here clobbers branches that were never (or not yet) in Hub.
    if (kittySession.ownsKittySession) {
      applyLiveMetaOnly(
        `owning_tab — keep Pinia SoT updated_at=${appliedUpdatedAt}`
      )
      return
    }

    // Children-only Hub snapshots (server voice preview) must not overwrite Pinia SoT.
    if (!hubHasCanonicalNodes && localNodes.length > 0) {
      applyLiveMetaOnly(
        `hub lacks nodes[] — keep Pinia SoT updated_at=${appliedUpdatedAt}`
      )
      return
    }

    // Never regress a richer local canvas (e.g. library load / autocomplete) to a
    // smaller Redis snapshot — especially before ownsKittySession is set on re-enter.
    if (hubHasCanonicalNodes && localNodes.length > hubNodes.length) {
      applyLiveMetaOnly(
        `local ahead hub (${localNodes.length}>${hubNodes.length}) — keep Pinia updated_at=${appliedUpdatedAt}`
      )
      return
    }

    const voiceFp = getKittyVoiceDiagramFingerprint(diagramData)
    const localFp = getKittyDiagramContentFingerprint(diagramStore.data)
    const hubContentFp = hubHasCanonicalNodes
      ? getKittyDiagramContentFingerprint({
          nodes: hubNodes,
          connections: Array.isArray((diagramData as Record<string, unknown>).connections)
            ? ((diagramData as Record<string, unknown>).connections as unknown[])
            : [],
        })
      : voiceFp
    const contentDiverged = hubContentFp.length > 0 && hubContentFp !== localFp
    const sseMissed =
      forceRecovery ||
      (Date.now() - lastDiagramSseAt.value > KITTY_LIVE_CONTEXT_POLL_MS * 2 && contentDiverged)

    if (sseMissed && diagramData != null && contentDiverged) {
      syncDiagramStoreFromVoiceContext(String(data.diagram_type ?? storeType), diagramData)
      traceKittyWorkflow(
        'desktop',
        'live_context_recovery',
        `updated_at=${appliedUpdatedAt} force=${forceRecovery}`,
        { scope: options.libraryDiagramId.value?.trim() }
      )
    } else if (sseMissed && diagramData != null && !contentDiverged) {
      traceKittyWorkflow(
        'desktop',
        'live_context_skip',
        `pinia already matches hub updated_at=${appliedUpdatedAt}`,
        { scope: options.libraryDiagramId.value?.trim() }
      )
    }

    if (
      Array.isArray(data.selected_nodes) &&
      data.selected_nodes.every((x) => typeof x === 'string')
    ) {
      applyKittyRemoteCanvasSelection(data.selected_nodes as string[], { canvasHighlight: true })
    }
    if ('selected_llm_model' in data) {
      void applyKittyRemoteLlmModel(data.selected_llm_model)
    }
    lastAppliedUpdatedAt.value = appliedUpdatedAt
  }

  async function tick(tickOpts?: { forceRecovery?: boolean }): Promise<void> {
    if (
      !options.syncEnabled.value ||
      options.collabSessionActive.value ||
      diagramStore.type == null
    ) {
      return
    }
    const id = options.libraryDiagramId.value
    if (id == null || id === '') {
      return
    }

    pollTickCount += 1
    // SSE carries hot diagram/selection; poll is recovery (every ~8 ticks ≈ 96s when live).
    const forceRecovery = tickOpts?.forceRecovery === true || pollTickCount % 8 === 0
    const mobileFresh = isKittyMobileActiveHubFresh()
    const sseFresh = Date.now() - lastDiagramSseAt.value < KITTY_LIVE_CONTEXT_POLL_MS * 2
    if (mobileFresh && sseFresh && !forceRecovery) {
      return
    }
    if (mobileFresh && !forceRecovery) {
      return
    }

    try {
      const res = await fetch(`/api/kitty/live_context/${encodeURIComponent(id)}`, {
        credentials: 'same-origin',
      })
      if (!res.ok) {
        return
      }

      const data = (await res.json()) as {
        ok?: boolean
        updated_at?: number
        diagram_type?: string
        diagram_data?: unknown
        selected_nodes?: unknown
        selected_llm_model?: unknown
      }

      if (!data.ok) {
        return
      }

      await tryRecoverDiagramFromLiveContext(data, forceRecovery)
    } catch {
      /* ignore transient network errors */
    }
  }

  function stopPolling(): void {
    pollingActive = false
    if (visibilityBound && typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibilityChange)
      visibilityBound = false
    }
    if (releaseHub != null) {
      releaseHub()
      releaseHub = null
    }
    if (pollTimer != null) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  function armNextPoll(): void {
    if (!pollingActive) {
      return
    }
    if (pollTimer != null) {
      clearTimeout(pollTimer)
    }
    pollTimer = setTimeout(() => {
      pollTimer = null
      void runPollCycle()
    }, KITTY_LIVE_CONTEXT_POLL_MS)
  }

  async function runPollCycle(): Promise<void> {
    if (!pollingActive) {
      return
    }
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
      armNextPoll()
      return
    }
    if (!tickInFlight) {
      tickInFlight = true
      try {
        await tick()
      } finally {
        tickInFlight = false
      }
    }
    armNextPoll()
  }

  function onVisibilityChange(): void {
    if (!pollingActive) {
      return
    }
    if (document.visibilityState === 'visible') {
      void runPollCycle()
    }
  }

  function startPolling(): void {
    stopPolling()
    pollingActive = true
    if (releaseHub == null) {
      releaseHub = acquireKittyMobileActiveHub()
    }
    pollTickCount = 0
    if (typeof document !== 'undefined' && !visibilityBound) {
      document.addEventListener('visibilitychange', onVisibilityChange)
      visibilityBound = true
    }
    void runPollCycle()
  }

  watch(
    () => options.syncEnabled.value,
    (on) => {
      if (on) {
        startPolling()
      } else {
        stopPolling()
        lastAppliedUpdatedAt.value = null
        lastDiagramSseAt.value = 0
      }
    },
    { immediate: true }
  )

  watch(
    () => mobileActiveHub.value.updatedAt,
    () => {
      if (!options.syncEnabled.value || !mobileActiveHub.value.active) {
        return
      }
      void tick()
    }
  )

  watch(
    () => options.libraryDiagramId.value,
    () => {
      lastAppliedUpdatedAt.value = null
      lastDiagramSseAt.value = 0
    }
  )

  eventBus.onWithOwner(
    'kitty:desktop_diagram_update',
    (payload) => {
      handleDiagramFanout(payload)
    },
    'KittyDesktopRemoteSync'
  )
  eventBus.onWithOwner(
    'kitty:desktop_canvas_action',
    (payload) => {
      handleCanvasActionFanout(payload)
    },
    'KittyDesktopRemoteSync'
  )
  eventBus.onWithOwner(
    'kitty:desktop_selection_update',
    (payload) => {
      handleSelectionFanout(payload)
    },
    'KittyDesktopRemoteSync'
  )
  eventBus.onWithOwner(
    'kitty:desktop_llm_model_update',
    (payload) => {
      handleLlmModelFanout(payload)
    },
    'KittyDesktopRemoteSync'
  )
  eventBus.onWithOwner(
    'kitty:hub_diagram_persisted',
    (payload: { scope?: string; revision?: number; source?: string }) => {
      if (!options.syncEnabled.value || collabBlocksDiagramEdits()) {
        return
      }
      const scope = typeof payload.scope === 'string' ? payload.scope.trim() : ''
      if (!scopeMatches(scope)) {
        return
      }
      // Owning tab already applied + verified into Pinia — reloading live_context
      // would clobber SoT with a stale/voice-shaped snapshot.
      if (payload.source === 'owning_tab') {
        lastDiagramSseAt.value = Date.now()
        traceKittyWorkflow('desktop', 'live_context_skip', 'owning_tab persist — keep Pinia', {
          scope,
        })
        return
      }
      void tick({ forceRecovery: true })
    },
    'KittyDesktopRemoteSync'
  )

  // Kitty autocomplete Hub-persists inside commitVerifiedLocalDiagramMutation.
  // Mark SSE fresh so live_context recovery does not treat the tab as stale.
  eventBus.onWithOwner(
    'kitty:diagram_action_completed',
    (payload: { ok: boolean }) => {
      if (!payload.ok || !options.syncEnabled.value) {
        return
      }
      if (!useKittySessionStore().ownsKittySession) {
        return
      }
      lastDiagramSseAt.value = Date.now()
    },
    'KittyDesktopRemoteSync'
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner('KittyDesktopRemoteSync')
    stopPolling()
  })

  return { refresh: tick }
}
