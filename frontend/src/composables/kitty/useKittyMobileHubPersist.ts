/**
 * Hub library persist for mobile Kitty — flush after verified diagram edits.
 * Pre-edit hub gate uses context-only sync in useMobileKittyChat (Redis live_spec).
 */
import { type ComputedRef, type Ref, onUnmounted, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSpecForSave } from '@/composables/editor/useDiagramSpecForSave'
import type {
  KittyAgentContext,
  KittyContextUpdateOptions,
} from '@/composables/kitty/kittyAgentTypes'
import { getKittyDiagramContentFingerprint } from '@/composables/kitty/kittyDiagramFingerprint'
import { recordPipelineEvent } from '@/composables/kitty/pipeline/trace'
import { SAVE } from '@/config'
import { useDiagramStore } from '@/stores/diagram'
import { useKittySessionStore } from '@/stores/kittySession'

export function useKittyMobileHubPersist(options: {
  libraryDiagramId: ComputedRef<string | null>
  diagramDisplayTitle: ComputedRef<string>
  isConnected: Ref<boolean>
  buildContext: () => KittyAgentContext
  updateContext: (context: KittyAgentContext, opts?: KittyContextUpdateOptions) => void
  onDebugLine?: (prefix: string, detail: string) => void
  /** Skip background persist while ASR → hub gate → sendText is running. */
  editPipelineActive?: Ref<boolean> | ComputedRef<boolean>
}): {
  flushHubLibraryPersist: () => void
} {
  const diagramStore = useDiagramStore()
  const kittySession = useKittySessionStore()
  const getDiagramSpec = useDiagramSpecForSave()
  const { promptLanguage } = useLanguage()

  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let lastPersistedFingerprint = ''
  let persistCounter = 0
  let pendingFingerprint: string | null = null
  let pendingIdempotencyKey: string | null = null

  function clearDebounce(): void {
    if (debounceTimer != null) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
  }

  function scheduleHubLibraryPersist(): void {
    if (options.editPipelineActive?.value) {
      return
    }
    clearDebounce()
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      if (options.editPipelineActive?.value) {
        return
      }
      flushHubLibraryPersist()
    }, SAVE.AUTO_SAVE_DEBOUNCE_MS)
  }

  function libraryTurnCtx(requestId: string, libId: string) {
    return {
      requestId,
      scope: libId,
      lane: 'mobile' as const,
    }
  }

  function sendHubLibraryPersist(fingerprint: string): boolean {
    const libId = options.libraryDiagramId.value?.trim() ?? ''
    if (!libId || diagramStore.type == null || !options.isConnected.value) {
      return false
    }
    if (!fingerprint || fingerprint === lastPersistedFingerprint) {
      return false
    }
    if (fingerprint === pendingFingerprint) {
      return false
    }
    const spec = getDiagramSpec()
    if (!spec || typeof spec !== 'object') {
      return false
    }

    persistCounter += 1
    const idempotencyKey = `kitty-mobile-persist-${libId}-${persistCounter}`

    const ctx = options.buildContext()
    const title =
      options.diagramDisplayTitle.value.trim() || ctx.diagram_display_title || 'Untitled'

    pendingFingerprint = fingerprint
    pendingIdempotencyKey = idempotencyKey

    options.updateContext(ctx, {
      persistLibrary: true,
      idempotencyKey,
      expectedRevision: kittySession.hubScopeRevision ?? undefined,
      librarySnapshot: {
        spec,
        title: String(title),
        language: promptLanguage.value,
      },
    })

    recordPipelineEvent({
      ctx: libraryTurnCtx(idempotencyKey, libId),
      module: 'library',
      step: 'S15_library_persist',
      status: 'started',
      detail: `lib=${libId.slice(0, 12)}`,
    })
    return true
  }

  function flushHubLibraryPersist(): void {
    if (options.editPipelineActive?.value) {
      return
    }
    const fingerprint = getKittyDiagramContentFingerprint(diagramStore.data)
    sendHubLibraryPersist(fingerprint)
  }

  function onContextMutationAck(data: {
    ok?: boolean
    revision?: number
    idempotency_key?: string
    persist_library?: boolean
    library_snapshot_saved?: boolean
    library_snapshot_error?: string
  }): void {
    const key = typeof data.idempotency_key === 'string' ? data.idempotency_key : ''
    if (!key || key !== pendingIdempotencyKey) {
      return
    }
    if (data.ok !== false && data.persist_library !== true) {
      pendingFingerprint = null
      pendingIdempotencyKey = null
      return
    }
    if (data.ok === false || data.library_snapshot_saved === false) {
      const detail = String(data.library_snapshot_error ?? 'mutation rejected').slice(0, 80)
      const libId = options.libraryDiagramId.value?.trim() ?? 'scope'
      // Soft fail: ring-buffer only — must not failKittyTurn / mutate active edit turn.
      recordPipelineEvent({
        ctx: libraryTurnCtx(key || `lib-${Date.now()}`, libId),
        module: 'library',
        step: 'S15_library_persist',
        status: 'fail',
        errorCode: 'library_snapshot_failed',
        detail,
      })
      pendingFingerprint = null
      pendingIdempotencyKey = null
      scheduleHubLibraryPersist()
      return
    }
    if (pendingFingerprint) {
      lastPersistedFingerprint = pendingFingerprint
    }
    pendingFingerprint = null
    pendingIdempotencyKey = null
    const libId = options.libraryDiagramId.value?.trim() ?? 'scope'
    recordPipelineEvent({
      ctx: libraryTurnCtx(key || `lib-${Date.now()}`, libId),
      module: 'library',
      step: 'S15_library_persist',
      status: 'ok',
      detail: 'library snapshot saved',
    })
  }

  const stopLibraryWatch = watch(options.libraryDiagramId, (next) => {
    lastPersistedFingerprint = ''
    pendingFingerprint = null
    pendingIdempotencyKey = null
    if (next?.trim()) {
      scheduleHubLibraryPersist()
    }
  })

  if (options.editPipelineActive != null) {
    watch(options.editPipelineActive, (active, wasActive) => {
      if (wasActive && !active) {
        scheduleHubLibraryPersist()
      }
    })
  }

  let wasConnected = options.isConnected.value
  watch(options.isConnected, (connected) => {
    // Clear on drop or reconnect so the next flush is not skipped by a stale fingerprint
    // (Vue may coalesce false→true in one tick, so do not rely on !wasConnected alone).
    if (!connected || (connected && !wasConnected)) {
      lastPersistedFingerprint = ''
      pendingFingerprint = null
      pendingIdempotencyKey = null
    }
    wasConnected = connected
  })

  function onVoiceDiagramUpdate(): void {
    if (!options.libraryDiagramId.value?.trim()) {
      return
    }
    scheduleHubLibraryPersist()
  }

  eventBus.onWithOwner(
    'voice:diagram_update_executed',
    onVoiceDiagramUpdate,
    'KittyMobileHubPersist'
  )
  eventBus.onWithOwner('voice:context_mutation_ack', onContextMutationAck, 'KittyMobileHubPersist')

  onUnmounted(() => {
    clearDebounce()
    flushHubLibraryPersist()
    stopLibraryWatch()
    eventBus.removeAllListenersForOwner('KittyMobileHubPersist')
  })

  return { flushHubLibraryPersist }
}
