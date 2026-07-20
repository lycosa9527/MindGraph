/** Session key for palette state scoped to diagram instance. */

export function getNodePaletteDiagramKey(
  diagramType: string,
  activeDiagramId: string | null,
  routeDiagramId: string | undefined
): string {
  const id = routeDiagramId || activeDiagramId || 'new'
  return `${diagramType}-${id}`
}

/** Session key for mind-map AI Brainstorm (AI头脑风暴), isolated from node palette. */
export function getAiBrainstormDiagramKey(
  activeDiagramId: string | null,
  routeDiagramId: string | undefined
): string {
  const id = routeDiagramId || activeDiagramId || 'new'
  return `ai-brainstorm-mindmap-${id}`
}
