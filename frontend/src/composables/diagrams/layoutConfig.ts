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

/** Default node width for rectangular nodes */
export const DEFAULT_NODE_WIDTH = 120

/** Default node height for rectangular nodes */
export const DEFAULT_NODE_HEIGHT = 50

/** Default topic node width for multi-flow maps (optimized for "事件" - 2 Chinese characters) */
export const MULTI_FLOW_MAP_TOPIC_WIDTH = 90

/** Event-pill font size (matches TopicNodeDiagram defaultStyle fallback). */
export const MULTI_FLOW_TOPIC_FONT_SIZE = 18

/** Event-pill horizontal padding: 18px each side. */
export const MULTI_FLOW_TOPIC_PADDING_X = 36

/**
 * Max inner label width for the multi-flow event pill.
 * Keep in sync with `topicMaxWidth` in `TopicNodeDiagram.vue`.
 */
export const MULTI_FLOW_TOPIC_LABEL_MAX_WIDTH = 300

/**
 * Max inner label width for multi-flow cause/effect pills (wrap cap).
 * Keep in sync with `flowMaxWidth` in `FlowNode.vue`.
 */
export const MULTI_FLOW_FLOW_NODE_LABEL_MAX_WIDTH = 250

/** Flow map minimum pill. The painted box grows with the label up to the caps below. */
export const FLOW_MAP_PILL_WIDTH = 120
export const FLOW_MAP_PILL_HEIGHT = 48

/**
 * Painted border-box caps. The stand-in width is clamped here so a pill is
 * not centered on a box wider than CSS allows. The browser's border box
 * replaces that stand-in. Keep in sync with the flow node `maxWidth` styles.
 */
export const FLOW_TOPIC_NODE_MAX_WIDTH = 400
export const FLOW_STEP_NODE_MAX_WIDTH = 300
export const FLOW_SUBSTEP_NODE_MAX_WIDTH = 230

/** Gap between flow map topic and first step */
export const FLOW_TOPIC_TO_STEP_GAP = 60

// ============================================================================
// Node Type-Specific Dimensions
// ============================================================================

/** TopicNode height (pill-shape with py-4 padding) */
export const TOPIC_NODE_HEIGHT = 52

/** Spacing between substep nodes (within a group) */
export const FLOW_SUBSTEP_SPACING = 12

/** Gap between step node and substep group (X offset) */
export const FLOW_SUBSTEP_OFFSET_X = 40

/** Gap between substep groups (Y spacing) */
export const FLOW_GROUP_GAP = 10

/** Minimum spacing between steps without substeps */
export const FLOW_MIN_STEP_SPACING = 40

/** Horizontal flow wraps onto the next row after this many steps. */
export const FLOW_MAP_STEPS_PER_ROW = 5

/** Clearance between a wrapped flow row and the row beneath it. */
export const FLOW_MAP_ROW_GAP = 72

/** How far a flow U-turn steps out past the node before it drops. */
export const FLOW_TURN_OUTSET_PX = 45

/** BranchNode height (mind-map default min-height baseline) */
export const BRANCH_NODE_HEIGHT = 34

/** LabelNode padding (4px 8px), summed over both sides. */
export const LABEL_NODE_PAD_X = 16
export const LABEL_NODE_PAD_Y = 8

/** Context node radius for circle maps */
export const DEFAULT_CONTEXT_RADIUS = 35

/** 双气泡图胶囊形状高度上限（px），超过后高度不再增大，长度仍随文字变化 */
export const DOUBLE_BUBBLE_MAX_CAPSULE_HEIGHT = 65

// ============================================================================
// Node Min Dimensions (for NodeResizer constraints)
// ============================================================================

/** Minimum dimensions per node type - used by NodeResizer min-width/min-height props */
export const NODE_MIN_DIMENSIONS = {
  topic: { minWidth: 120, minHeight: 48 },
  brace: { minWidth: 100, minHeight: 40 },
  branch: { minWidth: 90, minHeight: 34 },
  flow: { minWidth: 120, minHeight: 50 },
  bubble: { minWidth: 90, minHeight: 50 },
  label: { minWidth: 100, minHeight: 24 },
  circle: { minWidth: 80, minHeight: 80 },
} as const

// ============================================================================
// Spacing Defaults
// ============================================================================

/** Default vertical spacing between nodes */
export const DEFAULT_VERTICAL_SPACING = 60

/** Fixed vertical gap between the bottom edge of one sibling and the top edge
 *  of the next sibling within the same mind map branch.
 *  Box↔box default; v2 adaptive packing may use compact values for underlines. */
export const MINDMAP_SIBLING_GAP = 12

/** Vertical gap between top-level branches in a mind map.
 *  Larger than sibling spacing to visually separate independent branches.
 *  Box↔box default; v2 adaptive packing may use compact values for underlines. */
export const DEFAULT_MINDMAP_BRANCH_GAP = 28

/** v2: underline↔underline sibling gap (edge-to-edge AABB). */
export const MINDMAP_UNDERLINE_SIBLING_GAP = 6

/** v2: underline↔box (or box↔underline) sibling gap. */
export const MINDMAP_MIXED_SIBLING_GAP = 8

/** v2: underline↔underline L1 / cross-branch gap. */
export const MINDMAP_UNDERLINE_BRANCH_GAP = 14

/** v2: underline↔box L1 / cross-branch gap. */
export const MINDMAP_MIXED_BRANCH_GAP = 20

/** Mindmap column width (rank separation) - horizontal distance between depth levels. */
export const DEFAULT_MINDMAP_RANK_SEPARATION = 52

/** Minimum horizontal extent for mindmap curves. When layout produces smaller extent
 * (e.g. after branch move), scale both sides up to this for consistent curve length. */
export const MINDMAP_TARGET_EXTENT = 450

/** Brace map: tighter horizontal spacing between whole and parts */
export const BRACE_MAP_LEVEL_WIDTH = 60

/** Brace map: tighter vertical spacing between sibling parts */
export const BRACE_MAP_NODE_SPACING = 16

/** Brace pill CSS max-width. */
export const BRACE_NODE_MAX_WIDTH = 400

/**
 * Brace text column. 400 minus 18px padding each side and the 1.5px border
 * each side, so a line wraps inside the pill instead of past it.
 */
export const BRACE_NODE_CONTENT_MAX_WIDTH = BRACE_NODE_MAX_WIDTH - 18 * 2 - 3

/** Default column spacing for double bubble maps (topic-to-similarity, similarity-to-topic) */
export const DEFAULT_COLUMN_SPACING = 50

/** Tree map: reduced vertical spacing for tighter layout */
export const TREE_MAP_TOPIC_TO_CATEGORY_GAP = 50

/** Tree map: vertical gap between leaves in a group */
export const TREE_MAP_LEAF_SPACING = 10

/** Tree map: gap between category and first leaf */
export const TREE_MAP_CATEGORY_TO_LEAF_GAP = 24

/** Tree map: horizontal gap between category groups */
export const TREE_MAP_CATEGORY_SPACING = 60

/** Side spacing for multi-flow maps */
export const DEFAULT_SIDE_SPACING = 200
