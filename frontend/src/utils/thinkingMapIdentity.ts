/**
 * Dispatch leftover-alias resolve / migrate for the seven Thinking Maps.
 */
import type { Connection, DiagramNode, DiagramType, NodeStyle } from '@/types'
import { migrateBraceMapIdentityIds, resolveBraceMapAliasId } from '@/utils/braceMapIdentity'
import { migrateBridgeMapIdentityIds, resolveBridgeMapAliasId } from '@/utils/bridgeMapIdentity'
import { migrateBubbleMapIdentityIds, resolveBubbleMapAliasId } from '@/utils/bubbleMapIdentity'
import { migrateCircleMapIdentityIds, resolveCircleMapAliasId } from '@/utils/circleMapIdentity'
import {
  migrateDoubleBubbleMapIdentityIds,
  resolveDoubleBubbleMapAliasId,
} from '@/utils/doubleBubbleMapIdentity'
import { resolveFlowMapAliasId } from '@/utils/flowMapIdentity'
import { migrateFlowMapIdentityIds } from '@/utils/flowMapIdentityMigrate'
import {
  migrateMultiFlowMapIdentityIds,
  resolveMultiFlowMapAliasId,
} from '@/utils/multiFlowMapIdentity'
import type { ThinkingMapMigrateResult } from '@/utils/thinkingMapStableId'
import { migrateTreeMapIdentityIds, resolveTreeMapAliasId } from '@/utils/treeMapIdentity'

export function resolveThinkingMapAliasId(
  diagramType: DiagramType | string | null | undefined,
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  switch (diagramType) {
    case 'circle_map':
      return resolveCircleMapAliasId(hint, nodes)
    case 'bubble_map':
      return resolveBubbleMapAliasId(hint, nodes)
    case 'double_bubble_map':
      return resolveDoubleBubbleMapAliasId(hint, nodes)
    case 'tree_map':
      return resolveTreeMapAliasId(hint, nodes)
    case 'brace_map':
      return resolveBraceMapAliasId(hint, nodes)
    case 'flow_map':
      return resolveFlowMapAliasId(hint, nodes)
    case 'multi_flow_map':
      return resolveMultiFlowMapAliasId(hint, nodes)
    case 'bridge_map':
      return resolveBridgeMapAliasId(hint, nodes)
    default:
      return null
  }
}

export function migrateThinkingMapIdentityIds(
  diagramType: DiagramType | string,
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles?: Record<string, NodeStyle>
): ThinkingMapMigrateResult | null {
  switch (diagramType) {
    case 'circle_map':
      return migrateCircleMapIdentityIds(nodes, connections, nodeStyles)
    case 'bubble_map':
      return migrateBubbleMapIdentityIds(nodes, connections, nodeStyles)
    case 'double_bubble_map':
      return migrateDoubleBubbleMapIdentityIds(nodes, connections, nodeStyles)
    case 'tree_map':
      return migrateTreeMapIdentityIds(nodes, connections, nodeStyles)
    case 'brace_map':
      return migrateBraceMapIdentityIds(nodes, connections, nodeStyles)
    case 'flow_map':
      return migrateFlowMapIdentityIds(nodes, connections, nodeStyles)
    case 'multi_flow_map':
      return migrateMultiFlowMapIdentityIds(nodes, connections, nodeStyles)
    case 'bridge_map':
      return migrateBridgeMapIdentityIds(nodes, connections, nodeStyles)
    default:
      return null
  }
}
