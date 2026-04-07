/**
 * UI Configuration - Centralized constants for MindGraph UI
 *
 * This file provides a single source of truth for all UI-related constants,
 * eliminating magic numbers and ensuring consistency across the application.
 *
 * Usage:
 *   import { PANEL, ANIMATION, ZOOM, FIT_PADDING, PRESENTATION_Z } from '@/config/uiConfig'
 */

// ============================================================================
// Presentation tools — z-index stacking (laser, rail, timer overlay)
// ============================================================================
/**
 * Single z-index ladder for presentation UI. Higher paints above lower.
 * - Spotlight stays below the side rail so the rail stays clickable.
 * - Laser dot is above the rail (pointer-events: none on laser).
 * - Timer overlay is above canvas chrome; Teleport to `body` uses these values.
 * Element Plus overlays (dropdowns ~2000–3000) stay below this range.
 */
export const PRESENTATION_Z = {
  SPOTLIGHT: 99_998,
  SIDE_RAIL: 100_001,
  LASER: 100_100,
  /** Timer dim + countdown (Teleport to body; use inline style z-index) */
  TIMER_OVERLAY: 100_150,
} as const

/**
 * Canvas overlays Teleported to `body` (virtual keyboard, etc.).
 * Element Plus dropdowns/popovers are typically ~2000–3000; stay in that band, below `ElMessageBox` when possible.
 */
export const CANVAS_OVERLAY_Z = {
  /** Virtual keyboard panel fixed above safe area */
  VIRTUAL_KEYBOARD: 2040,
} as const

// ============================================================================
// Panel Dimensions (Tailwind-based)
// ============================================================================

/**
 * Panel width constants matching Tailwind classes
 * These must stay in sync with the actual CSS classes used in components
 */
export const PANEL = {
  /** Property panel width: w-80 = 20rem = 320px */
  PROPERTY_WIDTH: 320,
  /** MindMate panel width: w-96 = 24rem = 384px */
  MINDMATE_WIDTH: 384,
  /** Default `right` offset (px) for the floating MindMate panel from the viewport edge */
  MINDMATE_RIGHT_OFFSET_PX: 16,
  /** Node palette panel width: 50% of viewport when open (split layout with diagram) */
  NODE_PALETTE_WIDTH: 288,
  /** Node palette takes half the canvas area when open */
  NODE_PALETTE_HALF_WIDTH_PERCENT: 50,
  /** Node palette min width (px) */
  NODE_PALETTE_MIN_WIDTH: 320,
  /** Node palette max width (px) */
  NODE_PALETTE_MAX_WIDTH: 560,
} as const

// ============================================================================
// Animation/Transition Timing (milliseconds)
// ============================================================================

/**
 * Animation duration constants
 * Use these instead of hardcoded values like 300, 150, 50
 */
export const ANIMATION = {
  /** Long-press duration to trigger branch move (ms) */
  LONG_PRESS_MS: 1500,
  /** Fast animations: hover effects, small transitions */
  DURATION_FAST: 150,
  /** Normal animations: panel open/close, fit view */
  DURATION_NORMAL: 300,
  /** Slow animations: complex transitions */
  DURATION_SLOW: 500,
  /** Delay before panel-related actions (allow animation to start) */
  PANEL_DELAY: 50,
  /** Delay before fit view after node changes */
  FIT_DELAY: 100,
  /** Delay after fit view for viewport adjustment */
  FIT_VIEWPORT_DELAY: 350,
  /** Debounce delay for resize handlers */
  RESIZE_DEBOUNCE: 150,
} as const

// ============================================================================
// Zoom Configuration
// ============================================================================

/**
 * Zoom level constants for VueFlow canvas
 */
export const ZOOM = {
  /** Minimum zoom level (10%) */
  MIN: 0.1,
  /** Maximum zoom level (400%) */
  MAX: 4,
  /** Default zoom level (100%) */
  DEFAULT: 1,
  /** Zoom step multiplier for zoom in/out */
  STEP: 1.3,
} as const

// ============================================================================
// Fit View Padding
// ============================================================================

/**
 * Fit view padding - Vue Flow accepts pixels ("40px") or ratios (0.15)
 */
export const FIT_PADDING = {
  /** Standard padding ratio for normal fit view (15%) - used when mixing with panel calc */
  STANDARD: 0.15,
  /** Standard edge padding in pixels */
  STANDARD_PX: 40,
  /**
   * Right padding when the vertical presentation rail is visible: rail width + margin + buffer
   * so fit-to-canvas does not place content under PresentationSideToolbar.
   */
  PRESENTATION_SIDE_TOOLBAR_RIGHT_PX: 50,
  /**
   * Top padding in pixels — clears merged canvas chrome only (CanvasTopBar `min-h-12` = 48px).
   * Previously 64px when header and editing toolbar were separate rows; reclaimed for fit/zoom area.
   */
  TOP_UI_HEIGHT_PX: 48,
  /** Extra top padding for concept map - leaves space for menu icon above main topic node (icon ~20px + margin) */
  MAIN_TOPIC_MENU_ICON_PX: 35,
  /** Bottom padding in pixels - ZoomControls + AIModelSelector (bottom-4 + compact bar ~48px + margin) */
  BOTTOM_UI_HEIGHT_PX: 88,
  /** Extra bottom ratio for fitWithPanel (adds ~13% to base) */
  BOTTOM_UI_EXTRA: 0.13,
  /** Extra bottom padding (px) for tree map when alternative_dimensions overlay is shown below nodes */
  TREE_MAP_ALTERNATIVE_DIMENSIONS_EXTRA_PX: 70,
  /**
   * Standard padding with extra top/bottom for overlay UI.
   * Vue Flow object format: { top, right, bottom, left } - supports "40px" or ratio
   * top: clears merged canvas chrome; bottom: clears AI selector + Zoom controls
   */
  STANDARD_WITH_BOTTOM_UI: {
    top: '48px',
    right: '40px',
    bottom: '88px',
    left: '40px',
  } as const,
  /** Export padding for tight fit (5%) */
  EXPORT: 0.05,
  /** Minimal padding (2%) */
  MINIMAL: 0.02,
} as const

/**
 * Merged canvas chrome (CanvasTopBar + embedded CanvasToolbar): grid and truncation limits.
 * Use these for :style bindings or scoped CSS so layout stays consistent and adaptive.
 */
export const CANVAS_TOP_BAR = {
  /**
   * Two-tier compact chrome from `.canvas-top-bar` width (ResizeObserver).
   * 1) Below RIGHT_ACTIONS: MindMate / reset / export go icon-only first.
   * 2) Below TOOLBAR: editing toolbar labels hide (narrower still).
   */
  COMPACT_RIGHT_ACTIONS_BREAKPOINT_PX: 1100,
  COMPACT_TOOLBAR_BREAKPOINT_PX: 896,
  /** Left column (back + filename + auto-save): cap width so center toolbar keeps space */
  LEFT_CLUSTER_MAX_WIDTH: 'min(46vw, 17.5rem)',
  /** Auto-save line next to filename */
  AUTOSAVE_STATUS_MAX_WIDTH: 'min(11rem, 42vw)',
  /** Workshop participant name in header chip */
  PARTICIPANT_NAME_MAX_WIDTH_PX: 140,
  /** Filename display (non-edit); `ch` = width of "0" in font */
  FILENAME_DISPLAY_MAX_WIDTH: '12ch',
  /** Filename edit input cap inside left column */
  FILE_NAME_INPUT_MAX_WIDTH: 'min(12rem, 100%)',
} as const

/**
 * Panel inset - space reserved for floating overlays (top bar, toolbar, bottom controls).
 * Used for Node Palette and MindMate panel size/position to avoid overlap.
 */
export const PANEL_INSET = {
  /** Top inset (px) — align with FIT_PADDING.TOP_UI_HEIGHT_PX / merged header row */
  TOP: 48,
  /** Bottom inset (px) - clears AI selector + Zoom controls */
  BOTTOM: 88,
  /** Total vertical inset for max-height calc */
  get VERTICAL_TOTAL() {
    return this.TOP + this.BOTTOM
  },
} as const

// ============================================================================
// Canvas Configuration
// ============================================================================

/**
 * Default canvas size for layout calculations
 * Used when actual canvas dimensions are not available
 */
export const CANVAS = {
  /** Default canvas width */
  DEFAULT_WIDTH: 800,
  /** Default canvas height */
  DEFAULT_HEIGHT: 600,
  /** Default padding around canvas edges */
  DEFAULT_PADDING: 40,
} as const

// ============================================================================
// Snap Grid Configuration
// ============================================================================

/**
 * Grid settings for node snapping
 */
export const GRID = {
  /** Snap grid size [x, y] */
  SNAP_SIZE: [10, 10] as const,
  /** Background grid gap */
  BACKGROUND_GAP: 20,
  /** Background dot size */
  BACKGROUND_DOT_SIZE: 1,
} as const

// ============================================================================
// Breakpoints (matching Tailwind defaults)
// ============================================================================

/**
 * Responsive breakpoints for mobile/tablet detection
 */
export const BREAKPOINTS = {
  /** Mobile breakpoint (max-width) */
  MOBILE: 768,
  /** Tablet breakpoint (max-width) */
  TABLET: 1024,
  /** Desktop breakpoint (min-width) */
  DESKTOP: 1280,
} as const

// ============================================================================
// CSS Transition Strings
// ============================================================================

/**
 * Pre-built CSS transition strings for consistent animations
 */
export const CSS_TRANSITIONS = {
  /** Fast ease transition */
  FAST: '0.15s ease',
  /** Normal ease transition */
  NORMAL: '0.2s ease',
  /** Slow ease transition */
  SLOW: '0.3s ease',
} as const
