import type { DiagramNode, DiagramType } from '@/types'

import type { MindMapBranchSpec } from '@/utils/mindMapSubgraphMerge'

export type BraceMapClipboardNode = {
  text: string
  children: BraceMapClipboardNode[]
}

export type TreeMapClipboardPayload =
  | { kind: 'category'; text: string; leaves: { text: string }[] }
  | { kind: 'leaf'; text: string }

export type FlowMapClipboardPayload =
  | { kind: 'step'; step: string; substeps: string[] }
  | { kind: 'substep'; text: string }

export type HierarchicalClipboardPayload =
  | { kind: 'mindmap_branches'; branches: MindMapBranchSpec[] }
  | { kind: 'tree_map'; payload: TreeMapClipboardPayload }
  | { kind: 'brace_map'; subtree: BraceMapClipboardNode }
  | { kind: 'flow_map'; payload: FlowMapClipboardPayload }
  | { kind: 'flat_nodes'; nodes: DiagramNode[] }

export type HierarchicalClipboard = {
  sourceDiagramType: DiagramType
  payload: HierarchicalClipboardPayload
  /** Node ids removed on cut; used for history labels. */
  sourceNodeIds: string[]
}
