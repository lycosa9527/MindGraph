/**
 * While Mobile Kitty is linked to a library diagram, poll live_context so
 * desktop manual canvas edits reach phone Pinia (chips / context).
 */
import { type ComputedRef, type Ref, onUnmounted, watch } from 'vue'

import { applyKittyRemoteLlmModel } from '@/composables/kitty/applyKittyRemoteLlmModel'
import { hydrateMobileKittyFromLibrary } from '@/composables/kitty/hydrateMobileKittyFromLibrary'
import {
  getKittyDiagramContentFingerprint,
  getKittyVoiceDiagramFingerprint,
} from '@/composables/kitty/kittyDiagramFingerprint'
import { applyKittyRemoteCanvasSelection } from '@/composables/kitty/kittySelectionApply'
import { KITTY_PAIR_POLL_MS } from '@/composables/kitty/runKittyIntervalPoll'
import { syncDiagramStoreFromVoiceContext } from '@/composables/kitty/syncDiagramStoreFromVoiceContext'
import { useDiagramStore } from '@/stores/diagram'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function liveContextFingerprint(
  diagramType: string,
  diagramData: Record<string, unknown>
): string {
  const nodes = diagramData.nodes
  if (Array.isArray(nodes) && nodes.length > 0) {
    return `${diagramType}:${getKittyDiagramContentFingerprint({
      nodes,
      connections: Array.isArray(diagramData.connections) ? diagramData.connections : [],
    })}`
  }
  return `${diagramType}:${getKittyVoiceDiagramFingerprint(diagramData)}`
}

export function useMobileKittyLiveContextPoll(options: {
  /** Library diagram id when linked; null when ephemeral / unlinked. */
  libraryDiagramId: ComputedRef<string | null> | Ref<string | null>
  enabled: ComputedRef<boolean>
  /** Skip while ASR → sendText pipeline is running. */
  editPipelineActive: ComputedRef<boolean> | Ref<boolean>
  onDebugLine?: (prefix: string, detail: string) => void
}): void {
  const diagramStore = useDiagramStore()
  let intervalId: ReturnType<typeof setInterval> | null = null
  let inFlight = false
  let lastAppliedUpdatedAt: number | null = null
  let lastFingerprint = ''

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
      const res = await fetch(`/api/kitty/live_context/${encodeURIComponent(id)}`, {
        credentials: 'same-origin',
      })
      if (!res.ok) {
        return
      }
      const data: unknown = await res.json()
      if (!isRecord(data) || data.ok === false) {
        // Fall back to library row when live_spec is empty (desktop edits may only be saved).
        if (isRecord(data) && data.reason === 'no_live') {
          await hydrateMobileKittyFromLibrary(id)
        }
        return
      }
      const ua = data.updated_at
      if (typeof ua === 'number') {
        if (lastAppliedUpdatedAt != null && ua <= lastAppliedUpdatedAt) {
          return
        }
      }
      const diagramType = typeof data.diagram_type === 'string' ? data.diagram_type : ''
      const diagramData = isRecord(data.diagram_data) ? data.diagram_data : null
      if (diagramType && diagramData) {
        const fp = liveContextFingerprint(diagramType, diagramData)
        if (fp !== '' && fp === lastFingerprint) {
          if (typeof ua === 'number') {
            lastAppliedUpdatedAt = ua
          }
        } else {
          const applied = syncDiagramStoreFromVoiceContext(diagramType, diagramData)
          if (applied) {
            lastFingerprint = fp
            options.onDebugLine?.('#live', `hydrate ${id.slice(0, 8)}`)
          }
        }
      }
      if (
        Array.isArray(data.selected_nodes) &&
        data.selected_nodes.every((x) => typeof x === 'string')
      ) {
        const remote = data.selected_nodes as string[]
        const local = diagramStore.selectedNodes
        const same =
          remote.length === local.length && remote.every((nodeId, i) => nodeId === local[i])
        if (!same) {
          applyKittyRemoteCanvasSelection(remote, { canvasHighlight: false })
        }
      }
      if ('selected_llm_model' in data) {
        void applyKittyRemoteLlmModel(data.selected_llm_model)
      }
      if (typeof ua === 'number') {
        lastAppliedUpdatedAt = ua
      }
    } catch {
      /* best-effort */
    } finally {
      inFlight = false
    }
  }

  function start(): void {
    stop()
    void tick()
    intervalId = setInterval(() => {
      void tick()
    }, KITTY_PAIR_POLL_MS)
  }

  function stop(): void {
    if (intervalId != null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  watch(
    () =>
      [
        options.enabled.value,
        options.libraryDiagramId.value,
        options.editPipelineActive.value,
      ] as const,
    ([enabled, libId]) => {
      if (enabled && typeof libId === 'string' && libId.trim() !== '') {
        lastAppliedUpdatedAt = null
        lastFingerprint = ''
        start()
        return
      }
      stop()
    },
    { immediate: true }
  )

  onUnmounted(() => {
    stop()
  })
}
