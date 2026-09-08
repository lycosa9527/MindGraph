import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { parseMindMapCanvasMode, type MindMapCanvasMode, useUIStore } from '@/stores/ui'

function isMindMapDiagramType(type: string | null | undefined): boolean {
  return type === 'mindmap' || type === 'mind_map'
}

/** New-canvas layout, theme, and style bucket. Leftover stored `v3` maps to v2. */
export function isMindMapV2FamilyMode(mode: string): boolean {
  return parseMindMapCanvasMode(mode) === 'v2'
}

/** Layout engine key: leftover stored `v3` still uses the v2 columns. */
export function layoutMindMapCanvasMode(mode: string): MindMapCanvasMode {
  return parseMindMapCanvasMode(mode) ?? 'v2'
}

/** Read canvas mode from Pinia (for spec loaders and store slices outside Vue setup). */
export function readEffectiveMindMapCanvasMode(): MindMapCanvasMode {
  const uiStore = useUIStore()
  const featureFlagsStore = useFeatureFlagsStore()
  return effectiveMindMapCanvasMode(
    uiStore.mindMapCanvasMode,
    featureFlagsStore.getFeatureMindmapV2Canvas()
  )
}

/**
 * Showcase / public gallery policy: New canvas when the v2 feature flag is on;
 * Classic when the flag is off. Viewer Classic/New preference does not apply.
 */
export function readShowcaseMindMapCanvasMode(): MindMapCanvasMode {
  const featureFlagsStore = useFeatureFlagsStore()
  return featureFlagsStore.getFeatureMindmapV2Canvas() ? 'v2' : 'legacy'
}

/**
 * Effective canvas mode for a diagram session (flag clamp).
 * Prefer this over {@link readEffectiveMindMapCanvasMode} inside session-backed code.
 */
export function resolveSessionMindMapCanvasMode(sessionMode: string): MindMapCanvasMode {
  const featureFlagsStore = useFeatureFlagsStore()
  return effectiveMindMapCanvasMode(
    sessionMode,
    featureFlagsStore.getFeatureMindmapV2Canvas()
  )
}

/** True when the given session mode is New canvas after flag clamp. */
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

/** Classic is always available; leftover stored `v3` becomes v2. */
export function effectiveMindMapCanvasMode(
  mode: string,
  v2FeatureEnabled: boolean
): MindMapCanvasMode {
  const normalized = parseMindMapCanvasMode(mode) ?? 'v2'
  if (!v2FeatureEnabled && normalized === 'v2') {
    return 'legacy'
  }
  return normalized
}

export function isMindMapV2CanvasActive(
  diagramType: string | null | undefined,
  canvasMode: string,
  v2FeatureEnabled: boolean
): boolean {
  return (
    isMindMapDiagramType(diagramType) &&
    effectiveMindMapCanvasMode(canvasMode, v2FeatureEnabled) === 'v2'
  )
}
