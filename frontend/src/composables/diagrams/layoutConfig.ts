/**
 * Layout Configuration - Centralized default values for diagram layouts
 *
 * These values can be overridden by passing options to individual composables.
 * The defaults are chosen to work well with a standard 800x600 canvas.
 *
 * Dynamic canvas sizing: When the canvas size is known, composables should
 * recalculate positions based on actual dimensions. These defaults serve as
 * fallbacks when canvas dimensions are not available.
 *
 * Note: Canvas and animation constants are imported from @/config/uiConfig
 * for consistency across the application.
 */
import { CANVAS } from '@/config/uiConfig'

// ============================================================================
// Default Canvas Size (re-exported from uiConfig for backward compatibility)
// ============================================================================

/** Default canvas width for layout calculations */
export const DEFAULT_CANVAS_WIDTH = CANVAS.DEFAULT_WIDTH

/** Default canvas height for layout calculations */
export const DEFAULT_CANVAS_HEIGHT = CANVAS.DEFAULT_HEIGHT

/** Default canvas center X */
export const DEFAULT_CENTER_X = DEFAULT_CANVAS_WIDTH / 2 // 400

/** Default canvas center Y */
export const DEFAULT_CENTER_Y = DEFAULT_CANVAS_HEIGHT / 2 // 300

/** Default padding around canvas edges */
export const DEFAULT_PADDING = CANVAS.DEFAULT_PADDING

// ============================================================================
// Node Dimensions
// ============================================================================

/** Default topic/central node radius */
export const DEFAULT_TOPIC_RADIUS = 60

/** Default bubble node radius */
export const DEFAULT_BUBBLE_RADIUS = 40

/** Default node width for rectangular nodes */
export const DEFAULT_NODE_WIDTH = 120

/** Default node height for rectangular nodes */
export const DEFAULT_NODE_HEIGHT = 50

/** Default topic node width for multi-flow maps (optimized for "事件" - 2 Chinese characters) */
export const MULTI_FLOW_MAP_TOPIC_WIDTH = 90

// ============================================================================
// Node Type-Specific Dimensions
// ============================================================================

/** TopicNode height (pill-shape with py-4 padding) */
export const TOPIC_NODE_HEIGHT = 52

/** BraceNode height */
export const BRACE_NODE_HEIGHT = 40

/**
 * Flow Map Layout Constants
 * These are DEFAULT values for initial positioning.
 * Actual layout uses runtime measurement after nodes are rendered.
 * See useFlowMapLayout.ts for dynamic layout calculation.
 */

/** Default FlowNode height (used for initial layout, actual height measured at runtime) */
export const FLOW_NODE_HEIGHT = 50

/** FlowNode width */
export const FLOW_NODE_WIDTH = DEFAULT_NODE_WIDTH + 20 // 140

/** Default FlowSubstepNode height (used for initial layout, actual height measured at runtime) */
export const FLOW_SUBSTEP_NODE_HEIGHT = 50

/** FlowSubstepNode width (fixed for center alignment calculations) */
export const FLOW_SUBSTEP_NODE_WIDTH = 100

/** Spacing between substep nodes (within a group) */
export const FLOW_SUBSTEP_SPACING = 10

/** Gap between step node and substep group (X offset) */
export const FLOW_SUBSTEP_OFFSET_X = 40

/** Gap between substep groups (Y spacing) */
export const FLOW_GROUP_GAP = 10

/** Minimum spacing between steps without substeps */
export const FLOW_MIN_STEP_SPACING = 40

/** BranchNode height */
export const BRANCH_NODE_HEIGHT = 36

/** BubbleNode height */
export const BUBBLE_NODE_HEIGHT = 50

/** LabelNode height */
export const LABEL_NODE_HEIGHT = 24

/** Context node radius for circle maps */
export const DEFAULT_CONTEXT_RADIUS = 35

/** Difference bubble radius for double bubble maps */
export const DEFAULT_DIFF_RADIUS = 30

/** 双气泡图胶囊形状高度上限（px），超过后高度不再增大，长度仍随文字变化 */
export const DOUBLE_BUBBLE_MAX_CAPSULE_HEIGHT = 65

// ============================================================================
// Node Min Dimensions (for NodeResizer constraints)
// ============================================================================

/** Minimum dimensions per node type - used by NodeResizer min-width/min-height props */
export const NODE_MIN_DIMENSIONS = {
  topic: { minWidth: 120, minHeight: 48 },
  brace: { minWidth: 100, minHeight: 40 },
  branch: { minWidth: 80, minHeight: 36 },
  flow: { minWidth: 120, minHeight: 50 },
  bubble: { minWidth: 90, minHeight: 50 },
  label: { minWidth: 100, minHeight: 24 },
  circle: { minWidth: 80, minHeight: 80 },
} as const

// ============================================================================
// Spacing Defaults
// ============================================================================

/** Default horizontal spacing between nodes/levels */
export const DEFAULT_HORIZONTAL_SPACING = 180

/** Default vertical spacing between nodes */
export const DEFAULT_VERTICAL_SPACING = 60

/** Default step spacing for flow maps */
export const DEFAULT_STEP_SPACING = 200

/** Default level height for tree structures */
export const DEFAULT_LEVEL_HEIGHT = 100

/** Default level width for horizontal tree structures (brace maps) */
export const DEFAULT_LEVEL_WIDTH = 200

/** Default column spacing for double bubble maps (topic-to-similarity, similarity-to-topic) */
export const DEFAULT_COLUMN_SPACING = 50

/** Spacing between difference nodes and their topic in double bubble maps (left diff ↔ topic A, topic B ↔ right diff) */
export const DEFAULT_DIFF_TO_TOPIC_SPACING = 80

/** Default category spacing for tree maps */
export const DEFAULT_CATEGORY_SPACING = 160

/** Default leaf spacing for tree maps */
export const DEFAULT_LEAF_SPACING = 60

/** Topic to category gap for tree maps */
export const DEFAULT_TOPIC_TO_CATEGORY_GAP = 100

/** Category to leaf gap for tree maps */
export const DEFAULT_CATEGORY_TO_LEAF_GAP = 80

/** Pair spacing for bridge maps */
export const DEFAULT_PAIR_SPACING = 250

/** Side spacing for multi-flow maps */
export const DEFAULT_SIDE_SPACING = 200

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Calculate center position based on canvas dimensions
 */
export function calculateCenter(
  canvasWidth: number = DEFAULT_CANVAS_WIDTH,
  canvasHeight: number = DEFAULT_CANVAS_HEIGHT
): { centerX: number; centerY: number } {
  return {
    centerX: canvasWidth / 2,
    centerY: canvasHeight / 2,
  }
}

/**
 * Calculate start position for left-to-right layouts
 */
export function calculateStartPosition(padding: number = DEFAULT_PADDING): {
  startX: number
  startY: number
} {
  return {
    startX: padding + DEFAULT_NODE_WIDTH / 2,
    startY: padding + DEFAULT_NODE_HEIGHT / 2,
  }
}

/**
 * Calculate layout dimensions based on node count and spacing
 */
export function calculateRequiredDimensions(
  nodeCount: number,
  orientation: 'horizontal' | 'vertical' = 'horizontal',
  spacing: number = DEFAULT_STEP_SPACING,
  nodeSize: number = DEFAULT_NODE_WIDTH
): { width: number; height: number } {
  const contentSize = nodeCount * nodeSize + (nodeCount - 1) * spacing
  const padding = DEFAULT_PADDING * 2

  if (orientation === 'horizontal') {
    return {
      width: contentSize + padding,
      height: DEFAULT_CANVAS_HEIGHT,
    }
  } else {
    return {
      width: DEFAULT_CANVAS_WIDTH,
      height: contentSize + padding,
    }
  }
}
