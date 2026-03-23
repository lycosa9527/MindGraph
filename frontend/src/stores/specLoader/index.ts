/**
 * Spec Loader - Main entry point
 * Converts API spec format to DiagramData
 * Each diagram type has its own converter function
 *
 * This separates the spec-to-data conversion logic from the store,
 * making it easier to maintain and test each diagram type independently.
 */
import type { DiagramType } from '@/types'

import { loadBraceMapSpec } from './braceMap'
import { loadBridgeMapSpec } from './bridgeMap'
import { loadBubbleMapSpec } from './bubbleMap'
import { loadCircleMapSpec } from './circleMap'
import { loadConceptMapSpec } from './conceptMap'
import { loadDoubleBubbleMapSpec } from './doubleBubbleMap'
import { loadFlowMapSpec } from './flowMap'
import { loadGenericSpec } from './generic'
import { loadMindMapSpec } from './mindMap'
import { loadMultiFlowMapSpec } from './multiFlowMap'
import { loadTreeMapSpec } from './treeMap'
import type { SpecLoaderResult } from './types'
import { applyLearningSheetHiddenNodes } from './utils'

export { getDefaultTemplate } from './defaultTemplates'

// Re-export public APIs
export { recalculateBraceMapLayout } from './braceMap'
export { recalculateCircleMapLayout } from './circleMap'
export { recalculateBubbleMapLayout } from './bubbleMap'
export { recalculateMultiFlowMapLayout } from './multiFlowMap'
export {
  distributeBranchesClockwise,
  findBranchByNodeId,
  loadMindMapSpec,
  nodesAndConnectionsToMindMapSpec,
  normalizeMindMapHorizontalSymmetry,
} from './mindMap'
export type { SpecLoaderResult } from './types'

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
  diagramType: DiagramType
): SpecLoaderResult {
  let result: SpecLoaderResult

  // Check if this is a saved diagram (has nodes array)
  // Saved diagrams use generic format: { nodes: [...], connections: [...] }
  // LLM-generated specs use type-specific format: { topic, attributes, ... }
  if (Array.isArray(spec.nodes) && spec.nodes.length > 0) {
    result = loadGenericSpec(spec)
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
