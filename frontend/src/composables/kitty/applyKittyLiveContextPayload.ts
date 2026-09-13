/**
 * Apply a live_context GET / WS payload to Pinia (chips, selection, LLM).
 */
import { applyKittyRemoteLlmModel } from '@/composables/kitty/applyKittyRemoteLlmModel'
import { hydrateMobileKittyFromLibrary } from '@/composables/kitty/hydrateMobileKittyFromLibrary'
import {
  getKittyDiagramContentFingerprint,
  getKittyVoiceDiagramFingerprint,
} from '@/composables/kitty/kittyDiagramFingerprint'
import { applyKittyRemoteCanvasSelection } from '@/composables/kitty/kittySelectionApply'
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

export type KittyLiveContextApplyState = {
  lastAppliedUpdatedAt: number | null
  lastFingerprint: string
}

export async function applyKittyLiveContextPayload(
  data: unknown,
  state: KittyLiveContextApplyState,
  options?: {
    libraryDiagramId?: string
    onDebugLine?: (prefix: string, detail: string) => void
    canvasHighlight?: boolean
  }
): Promise<KittyLiveContextApplyState> {
  if (!isRecord(data) || data.ok === false) {
    if (isRecord(data) && data.reason === 'no_live' && options?.libraryDiagramId) {
      await hydrateMobileKittyFromLibrary(options.libraryDiagramId)
    }
    return state
  }
  const ua = data.updated_at
  if (typeof ua === 'number') {
    if (state.lastAppliedUpdatedAt != null && ua <= state.lastAppliedUpdatedAt) {
      return state
    }
  }
  let lastFingerprint = state.lastFingerprint
  let lastAppliedUpdatedAt = state.lastAppliedUpdatedAt
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
        const id = options?.libraryDiagramId ?? ''
        options?.onDebugLine?.('#live', `hydrate ${id.slice(0, 8)}`)
      }
    }
  }
  const diagramStore = useDiagramStore()
  if (
    Array.isArray(data.selected_nodes) &&
    data.selected_nodes.every((item) => typeof item === 'string')
  ) {
    const remote = data.selected_nodes as string[]
    const local = diagramStore.selectedNodes
    const same =
      remote.length === local.length && remote.every((nodeId, i) => nodeId === local[i])
    if (!same) {
      applyKittyRemoteCanvasSelection(remote, {
        canvasHighlight: options?.canvasHighlight === true,
      })
    }
  }
  if ('selected_llm_model' in data) {
    void applyKittyRemoteLlmModel(data.selected_llm_model)
  }
  if (typeof ua === 'number') {
    lastAppliedUpdatedAt = ua
  }
  return { lastAppliedUpdatedAt, lastFingerprint }
}
