/**
 * Desktop Kitty remote sync: incremental diagram_update + selection fanout / live_context poll.
 */
import { type ComputedRef, type Ref, onUnmounted, ref, watch } from 'vue'

import { applyKittyDiagramUpdate } from '@/composables/kitty/kittyAgentActions'
import {
  getKittyDiagramContentFingerprint,
  getKittyVoiceDiagramFingerprint,
} from '@/composables/kitty/kittyDiagramFingerprint'
import {
  acquireKittyMobileActiveHub,
  isKittyMobileActiveHubFresh,
  useKittyMobileActiveHubSnapshot,
} from '@/composables/kitty/kittyDesktopMobileActiveHub'
import { applyKittyRemoteCanvasSelection } from '@/composables/kitty/kittySelectionApply'
import { KITTY_PAIR_POLL_MS } from '@/composables/kitty/runKittyIntervalPoll'
import { syncDiagramStoreFromVoiceContext } from '@/composables/kitty/syncDiagramStoreFromVoiceContext'
import { eventBus } from '@/composables/core/useEventBus'
import { formatKittyDiagramUpdateDebug } from '@/composables/kitty/kittyAgentDebug'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import { useDiagramStore } from '@/stores/diagram'
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
}): { refresh: () => Promise<void> } {
  const diagramStore = useDiagramStore()
  const mobileActiveHub = useKittyMobileActiveHubSnapshot()
  const lastAppliedUpdatedAt = ref<number | null>(null)
  const lastDiagramSseAt = ref(0)
  let pollTickCount = 0
  let intervalId: ReturnType<typeof setInterval> | null = null
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
  }): void {
    if (!options.syncEnabled.value || collabBlocksDiagramEdits()) {
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
    lastDiagramSseAt.value = Date.now()
    const updates = isRecord(data.updates) || Array.isArray(data.updates) ? data.updates : {}
    const summary = formatKittyDiagramUpdateDebug(
      action,
      updates as Record<string, unknown>
    )
    traceKittyWorkflow('desktop', 'canvas_apply', summary, { scope, action })
    applyKittyDiagramUpdate(action, updates as Record<string, unknown>)
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
    if (lastAppliedUpdatedAt.value !== null && ua <= lastAppliedUpdatedAt.value) {
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
    const voiceFp = getKittyVoiceDiagramFingerprint(diagramData)
    const localFp = getKittyDiagramContentFingerprint(diagramStore.data)
    const sseMissed =
      forceRecovery ||
      (Date.now() - lastDiagramSseAt.value > KITTY_PAIR_POLL_MS * 2 &&
        voiceFp.length > 0 &&
        voiceFp !== localFp)

    if (sseMissed && diagramData != null) {
      syncDiagramStoreFromVoiceContext(String(data.diagram_type ?? storeType), diagramData)
      traceKittyWorkflow(
        'desktop',
        'live_context_recovery',
        `updated_at=${ua} force=${forceRecovery}`,
        { scope: options.libraryDiagramId.value?.trim() }
      )
    }

    if (
      Array.isArray(data.selected_nodes) &&
      data.selected_nodes.every((x) => typeof x === 'string')
    ) {
      applyKittyRemoteCanvasSelection(data.selected_nodes as string[], { canvasHighlight: true })
    }
    lastAppliedUpdatedAt.value = ua
  }

  async function tick(): Promise<void> {
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
    const forceRecovery = pollTickCount % 4 === 0
    const mobileFresh = isKittyMobileActiveHubFresh()
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
      }

      if (!data.ok) {
        return
      }

      await tryRecoverDiagramFromLiveContext(data, forceRecovery)
    } catch {
      /* ignore transient network errors */
    }
  }

  function startPolling(): void {
    stopPolling()
    if (releaseHub == null) {
      releaseHub = acquireKittyMobileActiveHub()
    }
    pollTickCount = 0
    void tick()
    intervalId = setInterval(() => {
      void tick()
    }, KITTY_PAIR_POLL_MS)
  }

  function stopPolling(): void {
    if (releaseHub != null) {
      releaseHub()
      releaseHub = null
    }
    if (intervalId != null) {
      clearInterval(intervalId)
      intervalId = null
    }
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
    'kitty:desktop_selection_update',
    (payload) => {
      handleSelectionFanout(payload)
    },
    'KittyDesktopRemoteSync'
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner('KittyDesktopRemoteSync')
    stopPolling()
  })

  return { refresh: tick }
}
