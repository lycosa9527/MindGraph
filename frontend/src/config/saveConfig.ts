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
  /** Max canvas spec size (KB), excluding saved model diagrams. Matches DIAGRAM_MAX_SPEC_SIZE_KB. */
  MAX_SPEC_SIZE_KB: 500,
  /**
   * Ceiling for a canvas that also stores model diagrams. The slot count is
   * however many models succeeded, not a fixed menu size. Matches
   * DIAGRAM_MAX_SPEC_WITH_LLM_RESULTS_KB.
   */
  MAX_SPEC_WITH_LLM_RESULTS_KB: 4000,
} as const

/** Session storage key for diagram import from `.mg` (landing page → canvas) */
export const IMPORT_SPEC_KEY = 'mindgraph_import_spec'
