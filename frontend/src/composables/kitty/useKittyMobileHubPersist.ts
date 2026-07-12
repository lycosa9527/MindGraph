/**
 * Hub library persist for mobile Kitty — flush after verified diagram edits and
 * await sync before voice/text edit turns (single hub gate; no duplicate pre-edit sync).
 */
import { type ComputedRef, type Ref, onUnmounted, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSpecForSave } from '@/composables/editor/useDiagramSpecForSave'
import type {
  KittyAgentContext,
  KittyContextUpdateOptions,
} from '@/composables/kitty/kittyAgentTypes'
import {
  type HubPersistResult,
  waitForContextMutationAck,
} from '@/composables/kitty/diagramEditHubPersist'
import { getKittyDiagramContentFingerprint } from '@/composables/kitty/kittyDiagramFingerprint'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import { SAVE } from '@/config'
import { useDiagramStore } from '@/stores/diagram'
import { useKittySessionStore } from '@/stores/kittySession'

const DEFAULT_EDIT_GATE_TIMEOUT_MS = 8000

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
  awaitHubLibraryPersistBeforeEdit: (timeoutMs?: number) => Promise<HubPersistResult>
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

    options.onDebugLine?.('#hub', `persist lib=${libId.slice(0, 8)} pending`)
    traceKittyWorkflow('hub', 'persist_send', `lib=${libId.slice(0, 12)}`, { scope: libId })
    return true
  }

  function flushHubLibraryPersist(): void {
    if (options.editPipelineActive?.value) {
      return
    }
    const fingerprint = getKittyDiagramContentFingerprint(diagramStore.data)
    sendHubLibraryPersist(fingerprint)
  }

  async function awaitHubLibraryPersistBeforeEdit(
    timeoutMs = DEFAULT_EDIT_GATE_TIMEOUT_MS
  ): Promise<HubPersistResult> {
    const libId = options.libraryDiagramId.value?.trim() ?? ''
    if (!libId || diagramStore.type == null) {
      return { ok: false, error: 'no_library_scope' }
    }
    if (!options.isConnected.value) {
      options.onDebugLine?.('#hub', 'edit gate skip ws closed')
      return { ok: false, error: 'not_connected' }
    }

    clearDebounce()
    const fingerprint = getKittyDiagramContentFingerprint(diagramStore.data)
    const rev = kittySession.hubScopeRevision
    if (fingerprint && fingerprint === lastPersistedFingerprint && pendingFingerprint == null) {
      options.onDebugLine?.('#hub', `edit gate ok cached rev=${rev ?? '?'}`)
      return { ok: true, revision: rev ?? undefined }
    }

    if (!sendHubLibraryPersist(fingerprint)) {
      if (fingerprint === lastPersistedFingerprint) {
        options.onDebugLine?.('#hub', `edit gate ok rev=${rev ?? '?'}`)
        return { ok: true, revision: rev ?? undefined }
      }
      options.onDebugLine?.('#hub', 'edit gate skip no spec')
      return { ok: false, error: 'hub_persist_skipped' }
    }

    const syncKey = pendingIdempotencyKey ?? ''
    options.onDebugLine?.('#hub', `edit gate pending rev=${rev ?? '?'}`)
    const result = await waitForContextMutationAck({
      idempotencyKey: syncKey,
      timeoutMs,
    })
    if (result.ok) {
      if (typeof result.revision === 'number') {
        kittySession.setHubScopeRevision(result.revision)
      }
      options.onDebugLine?.('#hub', `edit gate ok rev=${result.revision ?? '?'}`)
    } else {
      const err = result.error?.trim() || 'unknown'
      options.onDebugLine?.('#hub', `edit gate fail ${err.slice(0, 48)}`)
    }
    return result
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
      options.onDebugLine?.(
        '#hub',
        `persist failed ${String(data.library_snapshot_error ?? 'mutation rejected').slice(0, 40)}`
      )
      traceKittyWorkflow(
        'hub',
        'persist_ack',
        String(data.library_snapshot_error ?? 'mutation rejected').slice(0, 80),
        { scope: options.libraryDiagramId.value?.trim() }
      )
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
    options.onDebugLine?.('#hub', 'persist ack ok')
    traceKittyWorkflow('hub', 'persist_ack', 'library snapshot saved', {
      scope: options.libraryDiagramId.value?.trim(),
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

  return { flushHubLibraryPersist, awaitHubLibraryPersistBeforeEdit }
}
