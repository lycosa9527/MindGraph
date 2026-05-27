/**
 * Unified Kitty canvas selection apply (Pinia + optional Vue Flow highlight via event bus).
 */
import { eventBus } from '@/composables/core/useEventBus'
import { resolveKittySelectionNodeId } from '@/composables/kitty/kittyDiagramChildren'
import { useDiagramStore } from '@/stores/diagram'

export interface ApplyKittySelectionOptions {
  /** Emit selection events for Vue Flow pulse on desktop canvas. Default false (Pinia only). */
  canvasHighlight?: boolean
}

function resolveSelectionIds(
  diagramType: ReturnType<typeof useDiagramStore>['type'],
  nodes: Array<{ id: string }>,
  selectedNodes: string[]
): string[] {
  const resolved: string[] = []
  for (const raw of selectedNodes) {
    if (typeof raw !== 'string' || raw.length === 0) {
      continue
    }
    const id = resolveKittySelectionNodeId(diagramType, nodes, { nodeId: raw })
    if (id && !resolved.includes(id)) {
      resolved.push(id)
    }
  }
  return resolved
}

/** Apply voice / wheel / remote selection by node id or child index. */
export function applyKittySelectionTarget(
  target: { nodeId?: string; nodeIndex?: number },
  options: ApplyKittySelectionOptions = {}
): string | undefined {
  const diagramStore = useDiagramStore()
  const nodes = diagramStore.data?.nodes ?? []
  const resolved = resolveKittySelectionNodeId(diagramStore.type, nodes, target)
  if (!resolved) {
    return undefined
  }
  if (options.canvasHighlight) {
    eventBus.emit('selection:select_requested', { nodeId: resolved, nodeIndex: target.nodeIndex })
  } else {
    diagramStore.selectNodes([resolved])
  }
  return resolved
}

/** Apply remote selection fanout (desktop canvas — Vue Flow highlight + Pinia via bus). */
export function applyKittyRemoteCanvasSelection(
  selectedNodes: string[],
  options: ApplyKittySelectionOptions = { canvasHighlight: true }
): void {
  const diagramStore = useDiagramStore()
  const nodes = diagramStore.data?.nodes ?? []
  if (selectedNodes.length === 0) {
    if (options.canvasHighlight) {
      eventBus.emit('interaction:clear_selection_requested', {})
    } else {
      diagramStore.clearSelection()
    }
    return
  }
  const resolved = resolveSelectionIds(diagramStore.type, nodes, selectedNodes)
  if (resolved.length === 0) {
    return
  }
  if (options.canvasHighlight) {
    eventBus.emit('selection:select_requested', { nodeId: resolved[0] })
  } else {
    diagramStore.selectNodes(resolved)
  }
}
