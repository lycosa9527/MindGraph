/**
 * Skip library reload when ?diagramId= only syncs to the diagram already active
 * on the canvas.
 *
 * Cases:
 * - First autosave URL write after an unsaved canvas (Enter-added free-index
 *   mind-map ids). Reloading runs loadMindMapSpec renumbering, orphans the
 *   live selection (无法添加同级节点 / anchor_missing_parent_edge), and
 *   restacks L2 Y from estimates (children look vertically offset).
 * - First AutoComplete save while parallel LLM streams are still running
 *   (reload would clearCache/abort them).
 *
 * Sidebar diagram switches push a different id before activeDiagramId updates,
 * so they still load.
 */
export function shouldSkipLibraryReloadForActiveDiagram(
  routeDiagramId: string,
  activeDiagramId: string | null | undefined
): boolean {
  return Boolean(activeDiagramId) && routeDiagramId === activeDiagramId
}

/**
 * @deprecated Use {@link shouldSkipLibraryReloadForActiveDiagram}. Kept for
 * callers that still pass the generating flag; generating is no longer required.
 */
export function shouldSkipLibraryReloadDuringGeneration(
  _isGenerating: boolean,
  routeDiagramId: string,
  activeDiagramId: string | null | undefined
): boolean {
  return shouldSkipLibraryReloadForActiveDiagram(routeDiagramId, activeDiagramId)
}
