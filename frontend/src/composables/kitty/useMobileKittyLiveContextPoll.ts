/**
 * One-shot live_context GET on WS connect / library scope change.
 * Desktop canvas PUTs push ``live_context_update``; this is connect recovery only.
 */
import { type ComputedRef, type Ref, onUnmounted, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import {
  applyKittyLiveContextPayload,
  type KittyLiveContextApplyState,
} from '@/composables/kitty/applyKittyLiveContextPayload'
import { apiRequest } from '@/utils/apiClient'

export function useMobileKittyLiveContextPoll(options: {
  /** Library diagram id when linked; null when ephemeral / unlinked. */
  libraryDiagramId: ComputedRef<string | null> | Ref<string | null>
  enabled: ComputedRef<boolean>
  /** Skip while ASR → sendText pipeline is running. */
  editPipelineActive: ComputedRef<boolean> | Ref<boolean>
  /** One-shot GET when Kitty WS connects (and on library scope change). */
  wsConnected?: ComputedRef<boolean> | Ref<boolean>
  onDebugLine?: (prefix: string, detail: string) => void
}): void {
  let inFlight = false
  let state: KittyLiveContextApplyState = {
    lastAppliedUpdatedAt: null,
    lastFingerprint: '',
  }

  async function tick(): Promise<void> {
    if (!options.enabled.value || options.editPipelineActive.value) {
      return
    }
    const id = options.libraryDiagramId.value?.trim() ?? ''
    if (!id) {
      return
    }
    if (inFlight) {
      return
    }
    inFlight = true
    try {
      const res = await apiRequest(`/api/kitty/live_context/${encodeURIComponent(id)}`, {
        method: 'GET',
      })
      if (!res.ok) {
        return
      }
      const data: unknown = await res.json()
      state = await applyKittyLiveContextPayload(data, state, {
        libraryDiagramId: id,
        onDebugLine: options.onDebugLine,
      })
    } catch {
      /* best-effort */
    } finally {
      inFlight = false
    }
  }

  watch(
    () =>
      [
        options.enabled.value,
        options.libraryDiagramId.value,
        options.editPipelineActive.value,
        options.wsConnected?.value === true,
      ] as const,
    ([enabled, libId]) => {
      if (enabled && typeof libId === 'string' && libId.trim() !== '') {
        state = { lastAppliedUpdatedAt: null, lastFingerprint: '' }
        void tick()
      }
    },
    { immediate: true }
  )

  const onLivePush = (payload: { scope?: string; payload: Record<string, unknown> }) => {
    if (!options.enabled.value || options.editPipelineActive.value) {
      return
    }
    const id = options.libraryDiagramId.value?.trim() ?? ''
    if (!id) {
      return
    }
    const scope = payload.scope?.trim() ?? ''
    if (scope && scope !== id) {
      return
    }
    void applyKittyLiveContextPayload(payload.payload, state, {
      libraryDiagramId: id,
      onDebugLine: options.onDebugLine,
    }).then((next) => {
      state = next
    })
  }
  eventBus.on('kitty:live_context_update', onLivePush)
  onUnmounted(() => {
    eventBus.off('kitty:live_context_update', onLivePush)
  })
}
