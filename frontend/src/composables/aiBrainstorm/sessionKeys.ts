/** Session key for thinking-map and concept-map brainstorm, scoped to one diagram. */

export function getDiagramBrainstormKey(
  diagramType: string,
  activeDiagramId: string | null,
  routeDiagramId: string | undefined
): string {
  const id = routeDiagramId || activeDiagramId || 'new'
  return `${diagramType}-${id}`
}

/** Session key for the mind-map brainstorm sheet. Separate from thinking-map sessions. */
export function getAiBrainstormDiagramKey(
  activeDiagramId: string | null,
  routeDiagramId: string | undefined
): string {
  const id = routeDiagramId || activeDiagramId || 'new'
  return `ai-brainstorm-mindmap-${id}`
}
