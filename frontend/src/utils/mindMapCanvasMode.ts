import { useFeatureFlagsStore } from '@/stores/featureFlags'
import type { MindMapCanvasMode } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'

function isMindMapDiagramType(type: string | null | undefined): boolean {
  return type === 'mindmap' || type === 'mind_map'
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
export function resolveSessionMindMapCanvasMode(
  sessionMode: MindMapCanvasMode
): MindMapCanvasMode {
  return effectiveMindMapCanvasMode(
    sessionMode,
    useFeatureFlagsStore().getFeatureMindmapV2Canvas()
  )
}

/** True when the given session mode is New (v2) canvas after flag clamp. */
export function isSessionMindMapV2VisualDesignActive(
  sessionMode: MindMapCanvasMode
): boolean {
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

/** Classic canvas is always available; v2 requires the server feature flag. */
export function effectiveMindMapCanvasMode(
  mode: MindMapCanvasMode,
  v2FeatureEnabled: boolean
): MindMapCanvasMode {
  if (!v2FeatureEnabled && mode === 'v2') {
    return 'legacy'
  }
  return mode
}

export function isMindMapV2CanvasActive(
  diagramType: string | null | undefined,
  canvasMode: MindMapCanvasMode,
  v2FeatureEnabled: boolean
): boolean {
  return (
    isMindMapDiagramType(diagramType) &&
    effectiveMindMapCanvasMode(canvasMode, v2FeatureEnabled) === 'v2'
  )
}
