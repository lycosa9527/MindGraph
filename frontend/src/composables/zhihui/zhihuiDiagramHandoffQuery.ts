/**
 * Parse Canvas → ZhiHui 图示生图 handoff query params.
 */
export type ZhihuiDiagramHandoffQuery = {
  mode: 'diagram' | null
  diagramId: string | null
  diagramTitle: string | null
  /** When set, open an existing 图示生图 conversation instead of a blank create. */
  conversationId: string | null
}

function firstQueryValue(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) return value.trim()
  if (Array.isArray(value) && typeof value[0] === 'string' && value[0].trim()) {
    return value[0].trim()
  }
  return null
}

export function parseZhihuiDiagramHandoffQuery(
  query: Record<string, unknown>
): ZhihuiDiagramHandoffQuery {
  const modeRaw = firstQueryValue(query.mode)
  const diagramId =
    firstQueryValue(query.diagramId) || firstQueryValue(query.diagram_id)
  const diagramTitle = firstQueryValue(query.diagramTitle)
  const conversationId =
    firstQueryValue(query.conversationId) || firstQueryValue(query.conversation_id)
  const mode =
    modeRaw === 'diagram' || diagramId || conversationId ? 'diagram' : null
  return { mode, diagramId, diagramTitle, conversationId }
}

/** Keys to strip after applying a handoff so refresh does not re-apply. */
export const ZHIHUI_DIAGRAM_HANDOFF_QUERY_KEYS = [
  'mode',
  'diagramId',
  'diagram_id',
  'diagramTitle',
  'conversationId',
  'conversation_id',
] as const
