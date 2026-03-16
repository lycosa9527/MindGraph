/**
 * Save Configuration - Centralized constants for diagram save workflow
 *
 * Single source of truth for auto-save timing, suppression windows,
 * and size limits. Eliminates magic numbers across CanvasPage,
 * composables, and stores.
 */
export const SAVE = {
  /** Debounce delay before auto-save runs (ms) */
  AUTO_SAVE_DEBOUNCE_MS: 2000,
  /** Suppress auto-save after loading from library (ms) - avoids redundant save */
  SUPPRESS_AFTER_LOAD_MS: 500,
  /** Max spec size for backend (KB) - must match DIAGRAM_MAX_SPEC_SIZE_KB */
  MAX_SPEC_SIZE_KB: 500,
} as const
