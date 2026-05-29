/**
 * Debounced Hub library persist after mobile Kitty voice edits (Pinia spec → WS → Agent Hub).
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
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import { SAVE } from '@/config'
import { useDiagramStore } from '@/stores/diagram'

export function useKittyMobileHubPersist(options: {
  libraryDiagramId: ComputedRef<string | null>
  diagramDisplayTitle: ComputedRef<string>
  isConnected: Ref<boolean>
  buildContext: () => KittyAgentContext
  updateContext: (context: KittyAgentContext, opts?: KittyContextUpdateOptions) => void
  onDebugLine?: (prefix: string, detail: string) => void
}): { flushHubLibraryPersist: () => void } {
  const diagramStore = useDiagramStore()
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
    clearDebounce()
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      flushHubLibraryPersist()
    }, SAVE.AUTO_SAVE_DEBOUNCE_MS)
  }

  function flushHubLibraryPersist(): void {
    const libId = options.libraryDiagramId.value?.trim() ?? ''
    if (!libId || diagramStore.type == null) {
      return
    }
    const fingerprint = getKittyDiagramContentFingerprint(diagramStore.data)
    if (!fingerprint || fingerprint === lastPersistedFingerprint) {
      return
    }
    if (fingerprint === pendingFingerprint) {
      return
    }
    const spec = getDiagramSpec()
    if (!spec || typeof spec !== 'object') {
      return
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
      librarySnapshot: {
        spec,
        title: String(title),
        language: promptLanguage.value,
      },
    })

    options.onDebugLine?.('#hub', `persist lib=${libId.slice(0, 8)} pending`)
    traceKittyWorkflow('hub', 'persist_send', `lib=${libId.slice(0, 12)}`, { scope: libId })
  }

  function onContextMutationAck(data: {
    ok?: boolean
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

  const stopFingerprintWatch = watch(
    () => getKittyDiagramContentFingerprint(diagramStore.data),
    (next, prev) => {
      if (!next || prev === undefined || next === prev) {
        return
      }
      if (!options.libraryDiagramId.value?.trim()) {
        return
      }
      scheduleHubLibraryPersist()
    }
  )

  const stopLibraryWatch = watch(options.libraryDiagramId, (next) => {
    lastPersistedFingerprint = ''
    pendingFingerprint = null
    pendingIdempotencyKey = null
    if (next?.trim()) {
      scheduleHubLibraryPersist()
    }
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
    stopFingerprintWatch()
    stopLibraryWatch()
    eventBus.removeAllListenersForOwner('KittyMobileHubPersist')
  })

  return { flushHubLibraryPersist }
}
