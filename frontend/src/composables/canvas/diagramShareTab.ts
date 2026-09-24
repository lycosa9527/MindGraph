/**
 * Per-tab id for the shared-diagram edit lease.
 * sessionStorage keeps a second tab of the same user behind the first one.
 */
export const DIAGRAM_SHARE_TAB_KEY = 'mg-diagram-share-tab'

export function diagramShareTabId(): string {
  let id = sessionStorage.getItem(DIAGRAM_SHARE_TAB_KEY)
  if (!id) {
    id = crypto.randomUUID()
    sessionStorage.setItem(DIAGRAM_SHARE_TAB_KEY, id)
  }
  return id
}

export function diagramShareWriteHeaders(): Record<string, string> {
  try {
    const id = sessionStorage.getItem(DIAGRAM_SHARE_TAB_KEY)
    if (!id) return {}
    return { 'X-MG-Share-Tab': id }
  } catch {
    return {}
  }
}
