/** Session key for palette state scoped to diagram instance. */

export function getNodePaletteDiagramKey(
  diagramType: string,
  activeDiagramId: string | null,
  routeDiagramId: string | undefined
): string {
  const id = routeDiagramId || activeDiagramId || 'new'
  return `${diagramType}-${id}`
}

/** Session key for mind-map concept parking lot (概念停车场), isolated from node palette. */
export function getConceptParkingLotDiagramKey(
  activeDiagramId: string | null,
  routeDiagramId: string | undefined
): string {
  const id = routeDiagramId || activeDiagramId || 'new'
  return `concept-parking-lot-mindmap-${id}`
}
