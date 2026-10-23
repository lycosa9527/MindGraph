/**
 * Editor chrome. Every canvas uses the ribbon, including while the type is still loading.
 * There is no second toolbar to fall back to.
 */
import { isMindMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import { resolveSessionMindMapCanvasMode } from '@/utils/mindMapCanvasMode'

export function isCanvasEditorRibbonFamily(
  type: string | null | undefined,
  sessionCanvasMode: string
): boolean {
  if (type && isMindMapDiagramType(type)) {
    return resolveSessionMindMapCanvasMode(sessionCanvasMode) === 'v2'
  }
  return true
}
