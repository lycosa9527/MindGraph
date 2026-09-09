/**
 * Pure helpers for binding Voice Notes to the open canvas diagram.
 */
export function resolveCanvasDiagramId(input: {
  routeDiagramId: string | null
  activeDiagramId: string | null
}): string | null {
  const routeId = input.routeDiagramId?.trim() ?? ''
  if (routeId) return routeId
  const activeId = input.activeDiagramId?.trim() ?? ''
  return activeId || null
}

export function shouldReuseBoundVoiceNotes(input: {
  boundDiagramId: string | null
  targetDiagramId: string
  hasActiveCapture: boolean
  hasLocalTurns: boolean
}): boolean {
  if (input.boundDiagramId !== input.targetDiagramId) return false
  return input.hasActiveCapture || input.hasLocalTurns
}

export function shouldBlockDiagramRebind(input: {
  boundDiagramId: string | null
  targetDiagramId: string
  hasActiveCapture: boolean
}): boolean {
  if (!input.hasActiveCapture || !input.boundDiagramId) return false
  return input.boundDiagramId !== input.targetDiagramId
}

export function voiceNotesMarkdownUrl(packageId: number, ingestSource?: string): string {
  const path = `/api/doc-summary/${packageId}/md`
  if (!ingestSource) return path
  const params = new URLSearchParams({ ingest_source: ingestSource })
  return `${path}?${params.toString()}`
}
