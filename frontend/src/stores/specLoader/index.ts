/**
 * Spec Loader - Main entry point
 * Converts API spec format to DiagramData
 * Each diagram type has its own converter function
 *
 * This separates the spec-to-data conversion logic from the store,
 * making it easier to maintain and test each diagram type independently.
 */
import type { MindMapCanvasMode } from '@/stores/ui'
import type { DiagramType, NodeStyle } from '@/types'
import { migrateMindMapIdentityIds } from '@/utils/mindMapIdentityMigrate'

import { loadBraceMapSpec } from './braceMap'
import { loadBridgeMapSpec } from './bridgeMap'
import { loadBubbleMapSpec } from './bubbleMap'
import { loadCircleMapSpec } from './circleMap'
import { loadConceptMapSpec } from './conceptMap'
import { loadDoubleBubbleMapSpec } from './doubleBubbleMap'
import { loadFlowMapSpec } from './flowMap'
import { loadGenericSpec } from './generic'
import { loadMindMapSpec, nodesAndConnectionsToMindMapSpec } from './mindMap'
import { loadMultiFlowMapSpec } from './multiFlowMap'
import { loadTreeMapSpec } from './treeMap'
import { ensureTreeMapTopicLayout } from './treeMapTopicLayout'
import type { SpecLoaderResult } from './types'
import { applyLearningSheetHiddenNodes } from './utils'

export { getDefaultTemplate } from './defaultTemplates'

// Re-export public APIs
export { recalculateBraceMapLayout } from './braceMap'
export { recalculateBridgeMapLayout } from './bridgeMap'
export { recalculateCircleMapLayout } from './circleMap'
export { recalculateBubbleMapLayout } from './bubbleMap'
export { recalculateFlowMapLayout } from './flowMap'
export { recalculateMultiFlowMapLayout } from './multiFlowMap'
export { recalculateTreeMapLayout } from './treeMap'
export {
  distributeBranchesClockwise,
  findBranchByNodeId,
  loadMindMapSpec,
  mindMapBranchesClockwiseOrder,
  nodesAndConnectionsToMindMapSpec,
  normalizeMindMapHorizontalSymmetry,
  rebalanceMindMapBranchesAfterL1Delete,
  rebalanceMindMapBranchesIfLeftOnly,
} from './mindMap'
export type { LoadMindMapSpecOptions } from './mindMap'
export type { SpecLoaderResult } from './types'

/** Optional flags for {@link loadSpecForDiagramType}. */
export type LoadSpecForDiagramTypeOptions = {
  /**
   * Mind-map with stamped `nodes[]`+`connections[]`: keep laid-out positions via
   * generic load instead of re-running `loadMindMapSpec`. Default is true when
   * connections exist so identity, hiddenAnswer, and legacy ids survive reload.
   * Pass `false` to force extract + relayout.
   */
  preferLaidOutMindMapNodes?: boolean
  /** Session-owned mind-map canvas mode for initial layout (Showcase / export). */
  mindMapCanvasMode?: MindMapCanvasMode
}

/**
 * Load diagram data from API spec
 * @param spec - The API spec object
 * @param diagramType - The type of diagram
 * @returns SpecLoaderResult with nodes, connections, and optional metadata
 *
 * Note: Saved diagrams use a generic format with { nodes, connections },
 * while LLM-generated specs use type-specific formats (e.g., { topic, attributes }).
 * We detect saved diagrams by checking for the 'nodes' array and use loadGenericSpec.
 */
export function loadSpecForDiagramType(
  spec: Record<string, unknown>,
  diagramType: DiagramType,
  options?: LoadSpecForDiagramTypeOptions
): SpecLoaderResult {
  let result: SpecLoaderResult

  // Check if this is a saved diagram (has nodes array)
  // Saved diagrams use generic format: { nodes: [...], connections: [...] }
  // LLM-generated specs use type-specific format: { topic, attributes, ... }
  if (Array.isArray(spec.nodes) && spec.nodes.length > 0) {
    if (diagramType === 'mindmap' || diagramType === 'mind_map') {
      const hasConnections =
        Array.isArray(spec.connections) && (spec.connections as unknown[]).length > 0
      const generic = loadGenericSpec(spec)
      const styles =
        spec._node_styles && typeof spec._node_styles === 'object'
          ? (spec._node_styles as Record<string, NodeStyle>)
          : undefined
      const migrated = migrateMindMapIdentityIds(generic.nodes, generic.connections, styles)
      const styleMeta = migrated.nodeStyles
        ? { _node_styles: migrated.nodeStyles }
        : undefined
      // Soft path: saved / model-cache specs already have stable ids + positions.
      if (hasConnections && options?.preferLaidOutMindMapNodes !== false) {
        result = {
          ...generic,
          nodes: migrated.nodes,
          connections: migrated.connections,
          metadata: styleMeta ? { ...(generic.metadata || {}), ...styleMeta } : generic.metadata,
        }
      } else {
        const mindSpec = nodesAndConnectionsToMindMapSpec(migrated.nodes, migrated.connections)
        // Keep existing left/right sides. Redistributing via
        // [...left, ...right] + distributeBranchesClockwise is not idempotent and
        // reshuffles branches on every library reload / first autosave URL sync.
        const laidOut = loadMindMapSpec(
          { ...mindSpec, preserveLeftRight: true },
          { canvasMode: options?.mindMapCanvasMode }
        )
        result = {
          ...laidOut,
          metadata: styleMeta ? { ...(laidOut.metadata || {}), ...styleMeta } : laidOut.metadata,
        }
      }
    } else {
      result = loadGenericSpec(spec)
    }
    if (diagramType === 'tree_map') {
      result = { ...result, nodes: ensureTreeMapTopicLayout(result.nodes) }
    }
  } else if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    result = loadMindMapSpec(spec, { canvasMode: options?.mindMapCanvasMode })
  } else {
    const loader = SPEC_LOADERS[diagramType]
    result = loader ? loader(spec) : loadGenericSpec(spec)
  }

  return applyLearningSheetHiddenNodes(spec, result, diagramType)
}

// ============================================================================
// Loader Registry
// ============================================================================
const SPEC_LOADERS: Partial<
  Record<DiagramType, (spec: Record<string, unknown>) => SpecLoaderResult>
> = {
  circle_map: loadCircleMapSpec,
  bubble_map: loadBubbleMapSpec,
  double_bubble_map: loadDoubleBubbleMapSpec,
  tree_map: loadTreeMapSpec,
  flow_map: loadFlowMapSpec,
  multi_flow_map: loadMultiFlowMapSpec,
  brace_map: loadBraceMapSpec,
  bridge_map: loadBridgeMapSpec,
  concept_map: loadConceptMapSpec,
  mindmap: loadMindMapSpec,
  mind_map: loadMindMapSpec,
}
