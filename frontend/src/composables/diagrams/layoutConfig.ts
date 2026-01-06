/**
 * Layout Configuration - Centralized default values for diagram layouts
 *
 * These values can be overridden by passing options to individual composables.
 * The defaults are chosen to work well with a standard 800x600 canvas.
 *
 * Dynamic canvas sizing: When the canvas size is known, composables should
 * recalculate positions based on actual dimensions. These defaults serve as
 * fallbacks when canvas dimensions are not available.
 */

// ============================================================================
// Default Canvas Size
// ============================================================================

/** Default canvas width for layout calculations */
export const DEFAULT_CANVAS_WIDTH = 800

/** Default canvas height for layout calculations */
export const DEFAULT_CANVAS_HEIGHT = 600

/** Default canvas center X */
export const DEFAULT_CENTER_X = DEFAULT_CANVAS_WIDTH / 2 // 400

/** Default canvas center Y */
export const DEFAULT_CENTER_Y = DEFAULT_CANVAS_HEIGHT / 2 // 300

/** Default padding around canvas edges */
export const DEFAULT_PADDING = 40

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
export function calculateStartPosition(
  padding: number = DEFAULT_PADDING
): { startX: number; startY: number } {
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
