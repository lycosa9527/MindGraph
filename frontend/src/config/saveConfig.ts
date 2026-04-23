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
  /** Max interval between periodic saves (ms) - catches position/style-only edits */
  MAX_SAVE_INTERVAL_MS: 30_000,
  /** Suppress auto-save after loading from library (ms) - avoids redundant save */
  SUPPRESS_AFTER_LOAD_MS: 500,
  /** After server authoritative workshop snapshot — avoid stomping with stale autosave */
  SUPPRESS_AFTER_WORKSHOP_SNAPSHOT_MS: 5000,
  /** How often to refresh the relative "saved X ago" text (ms) */
  RELATIVE_TIME_TICK_MS: 10_000,
  /** Max spec size for backend (KB) - must match DIAGRAM_MAX_SPEC_SIZE_KB */
  MAX_SPEC_SIZE_KB: 500,
} as const

/** Session storage key for diagram import from `.mg` (landing page → canvas) */
export const IMPORT_SPEC_KEY = 'mindgraph_import_spec'
