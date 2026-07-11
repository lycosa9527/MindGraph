/**
 * True when ?diagramId= only synced after the first AutoComplete save for the
 * diagram already active on the canvas. Reloading would clearCache/abort the
 * remaining parallel LLM streams before they finish.
 */
export function shouldSkipLibraryReloadDuringGeneration(
  isGenerating: boolean,
  routeDiagramId: string,
  activeDiagramId: string | null | undefined
): boolean {
  return isGenerating && routeDiagramId === activeDiagramId
}
