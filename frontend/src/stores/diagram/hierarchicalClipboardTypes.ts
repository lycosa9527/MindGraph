import type { DiagramNode, DiagramType } from '@/types'
import type { MindMapBranchSpec } from '@/utils/mindMapSubgraphMerge'

export type BraceMapClipboardNode = {
  text: string
  textSecondary?: string
  children: BraceMapClipboardNode[]
}

export type TreeMapClipboardLeaf = { text: string; textSecondary?: string }

export type TreeMapClipboardPayload =
  | { kind: 'category'; text: string; textSecondary?: string; leaves: TreeMapClipboardLeaf[] }
  | { kind: 'leaf'; text: string; textSecondary?: string }

export type FlowMapClipboardPayload =
  | {
      kind: 'step'
      step: string
      stepSecondary?: string
      substeps: string[]
      substepsSecondary?: string[]
    }
  | { kind: 'substep'; text: string; textSecondary?: string }

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
