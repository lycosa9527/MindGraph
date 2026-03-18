import type { Ref } from 'vue'

import type { DiagramData, DiagramNode, DiagramType, HistoryEntry } from '@/types'

export type DiagramEventType =
  | 'diagram:node_added'
  | 'diagram:node_updated'
  | 'diagram:nodes_deleted'
  | 'diagram:selection_changed'
  | 'diagram:position_changed'
  | 'diagram:style_changed'
  | 'diagram:operation_completed'
  | 'diagram:layout_reset'
  | 'diagram:orientation_changed'

export interface DiagramEvent {
  type: DiagramEventType
  payload?: unknown
  timestamp: number
}

export type EventCallback = (event: DiagramEvent) => void

/** Left/right curve extent from center (for mind map branch tracking) */
export interface MindMapCurveExtents {
  left: number
  right: number
}

/**
 * Shared context passed to every slice factory.
 * Core state refs are set at creation; cross-cutting functions
 * are filled during two-phase initialisation in diagram.ts.
 */
export interface DiagramContext {
  // Core state refs
  type: Ref<DiagramType | null>
  data: Ref<DiagramData | null>
  selectedNodes: Ref<string[]>
  history: Ref<HistoryEntry[]>
  historyIndex: Ref<number>
  title: Ref<string>
  isUserEditedTitle: Ref<boolean>
  copiedNodes: Ref<DiagramNode[]>
  mindMapCurveExtentBaseline: Ref<MindMapCurveExtents | null>

  // Multi-flow layout state refs (Phase 4)
  nodeWidths: Ref<Record<string, number>>
  topicNodeWidth: Ref<number | null>
  multiFlowMapRecalcTrigger: Ref<number>
  sessionEditCount: Ref<number>

  // Cross-cutting functions (filled during two-phase init)
  pushHistory: (action: string) => void
  addNode: (node: DiagramNode) => void
  addConnection: (sourceId: string, targetId: string, label?: string) => string | null
  clearCustomPosition: (nodeId: string) => void
  clearNodeStyle: (nodeId: string) => void
  removeFromSelection: (nodeId: string) => void
  saveCustomPosition: (nodeId: string, x: number, y: number) => void
  loadFromSpec: (spec: Record<string, unknown>, diagramType: DiagramType) => boolean
  getDoubleBubbleSpecFromData: () => Record<string, unknown> | null
  buildFlowMapSpecFromNodes: () => Record<string, unknown> | null
  setNodeWidth: (nodeId: string, width: number | null) => void
  setDiagramType: (newType: DiagramType) => boolean
  resetSessionEditCount: () => void
  getMindMapDescendantIds: (rootNodeId: string) => Set<string>
  getTreeMapDescendantIds: (nodeId: string) => Set<string>
}
