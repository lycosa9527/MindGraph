/** Session key for palette state scoped to diagram instance. */

export function getNodePaletteDiagramKey(
  diagramType: string,
  activeDiagramId: string | null,
  routeDiagramId: string | undefined
): string {
  const id = routeDiagramId || activeDiagramId || 'new'
  return `${diagramType}-${id}`
}
