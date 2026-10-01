import { parseMindMapCanvasMode, type MindMapCanvasMode, useUIStore } from '@/stores/ui'

function isMindMapDiagramType(type: string | null | undefined): boolean {
  return type === 'mindmap' || type === 'mind_map'
}

/**
 * Archived layout bucket. The literal `legacy` key is not a user-facing mode;
 * stored classic is mapped to v2 by {@link parseMindMapCanvasMode}.
 */
export function isMindMapV2FamilyMode(mode: string): boolean {
  return mode === 'v2' || mode === 'v3'
}

/** Layout engine key. Leftover `v3` uses the v2 columns; `legacy` stays the archived bucket. */
export function layoutMindMapCanvasMode(mode: string): MindMapCanvasMode {
  if (mode === 'legacy') {
    return 'legacy'
  }
  return 'v2'
}

/** Read canvas mode from Pinia (for spec loaders and store slices outside Vue setup). */
export function readEffectiveMindMapCanvasMode(): MindMapCanvasMode {
  return effectiveMindMapCanvasMode(useUIStore().mindMapCanvasMode)
}

/** Showcase and export always use the new canvas. */
export function readShowcaseMindMapCanvasMode(): MindMapCanvasMode {
  return 'v2'
}

/**
 * Effective canvas mode for a diagram session.
 * Prefer this over {@link readEffectiveMindMapCanvasMode} inside session-backed code.
 */
export function resolveSessionMindMapCanvasMode(sessionMode: string): MindMapCanvasMode {
  return effectiveMindMapCanvasMode(sessionMode)
}

/** True when the given session mode is New canvas. */
export function isSessionMindMapV2VisualDesignActive(sessionMode: string): boolean {
  return resolveSessionMindMapCanvasMode(sessionMode) === 'v2'
}

/** V2 visual design from the viewer UI preference (editor chrome without a session). */
export function readMindMapV2VisualDesignActive(): boolean {
  return readEffectiveMindMapCanvasMode() === 'v2'
}

/** Legacy mind map canvas (pill nodes, curved per-branch connectors). */
export function readLegacyMindMapCanvasActive(): boolean {
  return readEffectiveMindMapCanvasMode() === 'legacy'
}

/** Leftover stored `v3` becomes v2. Unknown values default to the new canvas. */
export function effectiveMindMapCanvasMode(mode: string): MindMapCanvasMode {
  return parseMindMapCanvasMode(mode) ?? 'v2'
}

export function isMindMapV2CanvasActive(
  diagramType: string | null | undefined,
  canvasMode: string
): boolean {
  return isMindMapDiagramType(diagramType) && effectiveMindMapCanvasMode(canvasMode) === 'v2'
}
