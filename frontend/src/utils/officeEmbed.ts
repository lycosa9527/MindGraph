/**
 * Detect MindGraph running inside an Office (Word) add-in task pane / dialog,
 * or when opened with an explicit embed client query.
 *
 * Forces desktop layout (skip /m/*) for narrow WebView2 panes.
 */

const STORAGE_KEY = 'mg_office_embed_client'

let embedClientActive = ''

function readStorageClient(): string {
  if (typeof sessionStorage === 'undefined') {
    return ''
  }
  try {
    return sessionStorage.getItem(STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

function writeStorageClient(client: string): void {
  if (typeof sessionStorage === 'undefined' || !client) {
    return
  }
  try {
    sessionStorage.setItem(STORAGE_KEY, client)
  } catch {
    // ignore
  }
}

function isOfficeJsHost(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  const office = (window as Window & { Office?: { context?: unknown } }).Office
  return Boolean(office && office.context)
}

/**
 * Sync embed client from URL query / Office host / sessionStorage.
 * Call on boot and each navigation.
 */
export function syncOfficeEmbedFromSearch(
  search?: string | Record<string, unknown>
): string {
  let embedParam: string | null = null
  let clientParam: string | null = null

  if (typeof search === 'string') {
    const params = new URLSearchParams(
      search.startsWith('?') ? search : `?${search}`
    )
    embedParam = params.get('embed')
    clientParam = params.get('client')
  } else if (search && typeof search === 'object') {
    const embedRaw = search.embed
    const clientRaw = search.client
    embedParam = Array.isArray(embedRaw)
      ? String(embedRaw[0] ?? '')
      : embedRaw != null
        ? String(embedRaw)
        : null
    clientParam = Array.isArray(clientRaw)
      ? String(clientRaw[0] ?? '')
      : clientRaw != null
        ? String(clientRaw)
        : null
  } else if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search)
    embedParam = params.get('embed')
    clientParam = params.get('client')
  }

  const fromQuery =
    embedParam === 'word-addin' ||
    clientParam === 'word-addin'
      ? 'word-addin'
      : ''

  if (fromQuery) {
    embedClientActive = fromQuery
    writeStorageClient(fromQuery)
    return embedClientActive
  }

  // Prefer persisted embed flag before Office host sniffing so SPA navigations
  // inside the Word pane stay desktop even when Office.js is not on the page.
  const stored = readStorageClient()
  if (stored === 'word-addin') {
    embedClientActive = stored
    return embedClientActive
  }

  if (isOfficeJsHost()) {
    embedClientActive = 'word-addin'
    writeStorageClient(embedClientActive)
    return embedClientActive
  }

  embedClientActive = stored
  return embedClientActive
}

/** True when this tab should use desktop layout for an Office / word-addin embed. */
export function isOfficeEmbedDesktop(): boolean {
  if (embedClientActive || readStorageClient()) {
    return true
  }
  if (isOfficeJsHost()) {
    return true
  }
  return false
}

/** @deprecated Use isOfficeEmbedDesktop — kept for call-site migration. */
export function isWpsOfficeEmbed(): boolean {
  return isOfficeEmbedDesktop()
}

/** Test helper. */
export function resetOfficeEmbedForTests(): void {
  embedClientActive = ''
  if (typeof sessionStorage === 'undefined') {
    return
  }
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}
