import { useFeatureFlagsStore } from '@/stores/featureFlags'
import type { MindMapCanvasMode } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'

function isMindMapDiagramType(type: string | null | undefined): boolean {
  return type === 'mindmap' || type === 'mind_map'
}

/** V2 and V3 share layout, theme, and style bucket. V3 is bubble-style chrome only. */
export function isMindMapV2FamilyMode(mode: MindMapCanvasMode): boolean {
  return mode === 'v2' || mode === 'v3'
}

/** Layout engine key: V3 bubble chrome still uses the v2 columns. */
export function layoutMindMapCanvasMode(mode: MindMapCanvasMode): 'legacy' | 'v2' {
  return mode === 'legacy' ? 'legacy' : 'v2'
}

function v3CanvasFlagEnabled(store: ReturnType<typeof useFeatureFlagsStore>): boolean {
  return store.getFeatureMindmapV3Canvas()
}

/** Read canvas mode from Pinia (for spec loaders and store slices outside Vue setup). */
export function readEffectiveMindMapCanvasMode(): MindMapCanvasMode {
  const uiStore = useUIStore()
  const featureFlagsStore = useFeatureFlagsStore()
  return effectiveMindMapCanvasMode(
    uiStore.mindMapCanvasMode,
    featureFlagsStore.getFeatureMindmapV2Canvas(),
    v3CanvasFlagEnabled(featureFlagsStore)
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
export function resolveSessionMindMapCanvasMode(sessionMode: MindMapCanvasMode): MindMapCanvasMode {
  const featureFlagsStore = useFeatureFlagsStore()
  return effectiveMindMapCanvasMode(
    sessionMode,
    featureFlagsStore.getFeatureMindmapV2Canvas(),
    v3CanvasFlagEnabled(featureFlagsStore)
  )
}

/** True when the given session mode is New (v2) or V3 canvas after flag clamp. */
export function isSessionMindMapV2VisualDesignActive(sessionMode: MindMapCanvasMode): boolean {
  return isMindMapV2FamilyMode(resolveSessionMindMapCanvasMode(sessionMode))
}

/** V2 visual design from the viewer UI preference (editor chrome without a session). */
export function readMindMapV2VisualDesignActive(): boolean {
  return isMindMapV2FamilyMode(readEffectiveMindMapCanvasMode())
}

/** Legacy mind map canvas (pill nodes, curved per-branch connectors). */
export function readLegacyMindMapCanvasActive(): boolean {
  return readEffectiveMindMapCanvasMode() === 'legacy'
}

/** Classic is always available; v2/v3 require their server feature flags. */
export function effectiveMindMapCanvasMode(
  mode: MindMapCanvasMode,
  v2FeatureEnabled: boolean,
  v3FeatureEnabled: boolean = true
): MindMapCanvasMode {
  if (!v2FeatureEnabled && isMindMapV2FamilyMode(mode)) {
    return 'legacy'
  }
  if (!v3FeatureEnabled && mode === 'v3') {
    return 'v2'
  }
  return mode
}

export function isMindMapV2CanvasActive(
  diagramType: string | null | undefined,
  canvasMode: MindMapCanvasMode,
  v2FeatureEnabled: boolean,
  v3FeatureEnabled: boolean = true
): boolean {
  return (
    isMindMapDiagramType(diagramType) &&
    effectiveMindMapCanvasMode(canvasMode, v2FeatureEnabled, v3FeatureEnabled) === 'v2'
  )
}
