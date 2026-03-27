/**
 * Barrel exports for `@/components` (subset only).
 *
 * Policy:
 * - Re-export domains that are imported across many routes or used as the primary “shell” UI
 *   (auth, sidebar, mindgraph landing, canvas chrome, shared panels, community).
 * - Feature-specific areas (e.g. diagram, admin, knowledge-space, library, debateverse,
 *   workshop-chat) are intentionally omitted from this barrel to avoid name collisions,
 *   keep tree-shaking predictable, and make ownership of imports obvious.
 * - Import those with explicit paths, e.g. `@/components/diagram/DiagramCanvas.vue`.
 */
export * from './auth'
export * from './panels'
export * from './common'
export * from './sidebar'
export * from './mindgraph'
export * from './canvas'
export * from './community'
