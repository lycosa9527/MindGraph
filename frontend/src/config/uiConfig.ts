/**
 * UI Configuration - Centralized constants for MindGraph UI
 *
 * This file provides a single source of truth for all UI-related constants,
 * eliminating magic numbers and ensuring consistency across the application.
 *
 * Usage:
 *   import { PANEL, ANIMATION, ZOOM, FIT_PADDING } from '@/config/uiConfig'
 */

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
  /** Node palette panel width: w-72 = 18rem = 288px */
  NODE_PALETTE_WIDTH: 288,
} as const

// ============================================================================
// Animation/Transition Timing (milliseconds)
// ============================================================================

/**
 * Animation duration constants
 * Use these instead of hardcoded values like 300, 150, 50
 */
export const ANIMATION = {
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
 * Padding ratios for fitView operations
 * These are percentages of the viewport size
 */
export const FIT_PADDING = {
  /** Standard padding for normal fit view (15%) */
  STANDARD: 0.15,
  /** Export padding for tight fit (5%) */
  EXPORT: 0.05,
  /** Minimal padding (2%) */
  MINIMAL: 0.02,
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
