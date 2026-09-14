/**
 * Tab-scoped canvas-collab restore keys.
 *
 * Survive refresh of the same diagram. Must not survive gallery / new-map
 * navigation or a library switch to a different diagram.
 */

export const WORKSHOP_SESSION_CODE_KEY = 'mg_workshop_code'
export const WORKSHOP_SESSION_DIAGRAM_KEY = 'mg_workshop_diagram_id'

export function clearWorkshopSessionStorage(): void {
  sessionStorage.removeItem(WORKSHOP_SESSION_CODE_KEY)
  sessionStorage.removeItem(WORKSHOP_SESSION_DIAGRAM_KEY)
}

export function persistWorkshopSession(code: string, diagramId: string): void {
  sessionStorage.setItem(WORKSHOP_SESSION_CODE_KEY, code)
  sessionStorage.setItem(WORKSHOP_SESSION_DIAGRAM_KEY, diagramId)
}

export function readWorkshopSession(): { code: string; diagramId: string } | null {
  const code = sessionStorage.getItem(WORKSHOP_SESSION_CODE_KEY)?.trim() ?? ''
  const diagramId = sessionStorage.getItem(WORKSHOP_SESSION_DIAGRAM_KEY)?.trim() ?? ''
  if (!code || !diagramId) {
    return null
  }
  return { code, diagramId }
}

export function firstQueryString(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) {
    return value.trim()
  }
  if (Array.isArray(value) && typeof value[0] === 'string' && value[0].trim()) {
    return value[0].trim()
  }
  return null
}

export function routeDiagramIdFromQuery(query: Record<string, unknown>): string | null {
  return firstQueryString(query.diagramId) ?? firstQueryString(query.diagram_id)
}

/** True when the URL is a new blank canvas, not a refresh of the collab diagram. */
export function isNewCanvasNavigationQuery(query: Record<string, unknown>): boolean {
  if (firstQueryString(query.import)) {
    return true
  }
  const type = firstQueryString(query.type)
  return Boolean(type) && !routeDiagramIdFromQuery(query)
}

/**
 * Refresh of the same library diagram only. A missing ``diagramId`` must
 * never count as a match — that re-attached the last room from the gallery.
 */
export function shouldRestoreWorkshopSession(query: Record<string, unknown>): boolean {
  const saved = readWorkshopSession()
  if (!saved) {
    return false
  }
  if (firstQueryString(query.join_workshop)) {
    return false
  }
  const routeDiagramId = routeDiagramIdFromQuery(query)
  return routeDiagramId === saved.diagramId
}

/** Next query that pins the live room to ``?diagramId=`` so refresh can restore. */
export function queryWithSessionDiagramId(
  query: Record<string, unknown>,
  diagramId: string
): Record<string, unknown> | null {
  if (routeDiagramIdFromQuery(query) === diagramId) {
    return null
  }
  const next: Record<string, unknown> = { ...query, diagramId }
  delete next.diagram_id
  delete next.join_workshop
  return next
}

export function isCanvasEditorPath(path: string): boolean {
  return path === '/canvas' || path === '/m/canvas'
}

/**
 * Drop the stored room when leaving canvas, opening a new/different map, or
 * entering canvas from another in-app page (gallery → new mind map).
 * Initial load / F5 has no matched ``from`` route — do not clear, so refresh
 * of the same tab can restore.
 */
export function shouldClearWorkshopSessionOnNavigate(
  fromPath: string,
  toPath: string,
  toQuery: Record<string, unknown>,
  fromHadMatchedRoute = false
): boolean {
  const fromCanvas = isCanvasEditorPath(fromPath)
  const toCanvas = isCanvasEditorPath(toPath)
  if (fromCanvas && !toCanvas) {
    return true
  }
  const canvasToCanvas = fromCanvas && toCanvas
  const enterCanvasFromApp = !fromCanvas && toCanvas && fromHadMatchedRoute
  if (!canvasToCanvas && !enterCanvasFromApp) {
    return false
  }
  if (isNewCanvasNavigationQuery(toQuery)) {
    return true
  }
  const toId = routeDiagramIdFromQuery(toQuery)
  if (enterCanvasFromApp && !toId) {
    return true
  }
  const saved = readWorkshopSession()
  return Boolean(saved && toId && toId !== saved.diagramId)
}
