/** HTML5 drag data type for creating a new concept link from a concept node (source = node id). */
export const CONCEPT_LINK_DATA_TYPE = 'application/mindgraph-concept-link'

/**
 * HTML5 drag payload for a new link originating at a relationship label (JSON in dataTransfer).
 * The graph still stores node–node edges; anchor is chosen from the two endpoints.
 */
export const CONCEPT_LINK_FROM_RELATIONSHIP_TYPE =
  'application/mindgraph-concept-link-from-relationship'

export type RelationshipLinkDragPayload = {
  connectionId: string
  sourceNodeId: string
  targetNodeId: string
  labelX: number
  labelY: number
}
