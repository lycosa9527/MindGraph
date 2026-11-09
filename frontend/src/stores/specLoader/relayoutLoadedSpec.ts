/**
 * Layout pass for a spec right after load and `attachRemainingSecondary`.
 * Some loaders place nodes before the second language is attached, so a fresh
 * spec gets a full recalc here and the stored positions match the canvas.
 * A saved canvas keeps its stored positions, except bubble maps, which always re-pack.
 */
import type { DiagramNode, DiagramType } from '@/types'

import { recalculateBraceMapLayout } from './braceMap'
import { recalculateBridgeMapLayout } from './bridgeMap'
import { recalculateBubbleMapLayout } from './bubbleMap'
import { recalculateFlowMapLayout } from './flowMap'
import { recalculateMultiFlowMapLayout } from './multiFlowMap'
import { recalculateTreeMapLayout } from './treeMap'
import type { SpecLoaderResult } from './types'

export function relayoutLoadedSpecNodes(
  diagramType: DiagramType,
  result: SpecLoaderResult,
  savedCanvas: boolean
): DiagramNode[] {
  const { nodes, connections } = result
  if (diagramType === 'bubble_map') {
    return nodes.length > 0 ? recalculateBubbleMapLayout(nodes) : nodes
  }
  if (savedCanvas) return nodes
  switch (diagramType) {
    case 'flow_map':
      return recalculateFlowMapLayout(nodes)
    case 'tree_map':
      return recalculateTreeMapLayout(nodes)
    case 'brace_map':
      return recalculateBraceMapLayout(nodes, connections, {})
    case 'bridge_map':
      return recalculateBridgeMapLayout(nodes, {})
    case 'multi_flow_map':
      return recalculateMultiFlowMapLayout(nodes)
    default:
      return nodes
  }
}
