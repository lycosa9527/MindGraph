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

/** V2 visual design: unified connection color, theme presets, node shapes, geometry. */
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
