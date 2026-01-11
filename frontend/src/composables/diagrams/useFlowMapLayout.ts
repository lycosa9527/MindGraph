/**
 * useFlowMapLayout - Flow map layout configuration
 *
 * Flow maps now use fixed node dimensions (width: 140px/100px, height: 50px).
 * Layout is fully deterministic and calculated in specLoader.ts at load time.
 *
 * This file exports layout constants for consistency across the codebase.
 * The measurement-based recalculation has been removed in favor of fixed dimensions
 * for better performance (single render cycle, no DOM queries).
 *
 * Node dimensions:
 * - FlowNode: 140px x 50px (fixed)
 * - FlowSubstepNode: 100px x 50px (fixed)
 * - Text is truncated with ellipsis when it exceeds available width
 */
// Import layout constants from layoutConfig
import {
  DEFAULT_CENTER_X,
  DEFAULT_PADDING,
  FLOW_GROUP_GAP,
  FLOW_MIN_STEP_SPACING,
  FLOW_NODE_HEIGHT,
  FLOW_NODE_WIDTH,
  FLOW_SUBSTEP_NODE_HEIGHT,
  FLOW_SUBSTEP_NODE_WIDTH,
  FLOW_SUBSTEP_OFFSET_X,
  FLOW_SUBSTEP_SPACING,
} from './layoutConfig'

// Re-export layout constants for convenience
export {
  DEFAULT_CENTER_X,
  DEFAULT_PADDING,
  FLOW_GROUP_GAP,
  FLOW_MIN_STEP_SPACING,
  FLOW_NODE_HEIGHT,
  FLOW_NODE_WIDTH,
  FLOW_SUBSTEP_NODE_HEIGHT,
  FLOW_SUBSTEP_NODE_WIDTH,
  FLOW_SUBSTEP_OFFSET_X,
  FLOW_SUBSTEP_SPACING,
}

/**
 * Flow map layout composable
 *
 * With fixed node dimensions, layout is now deterministic and handled by specLoader.
 * This composable is kept for API compatibility but no longer performs runtime calculations.
 */
export function useFlowMapLayout() {
  return {
    // Constants are now the source of truth - no measurement needed
    nodeWidth: FLOW_NODE_WIDTH,
    nodeHeight: FLOW_NODE_HEIGHT,
    substepWidth: FLOW_SUBSTEP_NODE_WIDTH,
    substepHeight: FLOW_SUBSTEP_NODE_HEIGHT,
  }
}
