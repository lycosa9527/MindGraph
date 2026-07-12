/**
 * Optional in-page mobile console (Eruda) for iOS Safari debugging.
 *
 * Enable:
 * - Open any page with ``?eruda=1`` (persists in localStorage)
 * - Or set ``localStorage.setItem('mg_eruda', '1')`` then reload
 * - Auto-on for ``test.*`` / localhost hosts (disable with ``?eruda=0``)
 *
 * Eruda is served from ``public/debug/eruda.js`` and injected only when enabled
 * (not a Vite/Rolldown dependency — avoids build failures if npm install is stale).
 */
const STORAGE_KEY = 'mg_eruda'
const ERUDA_SCRIPT_ATTR = 'data-mg-eruda'

let loadStarted = false

function hostnameSuggestsDebugHost(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  const host = window.location.hostname.toLowerCase()
  return (
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host.startsWith('test.') ||
    host.includes('.test.')
  )
}

export function isMobileDebugConsoleEnabled(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  try {
    const params = new URLSearchParams(window.location.search)
    if (params.get('eruda') === '0' || params.get('debugConsole') === '0') {
      return false
    }
    if (params.get('eruda') === '1' || params.get('debugConsole') === '1') {
      return true
    }
    if (window.localStorage.getItem(STORAGE_KEY) === '1') {
      return true
    }
  } catch {
    /* private mode / blocked storage */
  }
  return hostnameSuggestsDebugHost()
}

function persistEnableFromQuery(): void {
  if (typeof window === 'undefined') {
    return
  }
  try {
    const params = new URLSearchParams(window.location.search)
    if (params.get('eruda') === '1' || params.get('debugConsole') === '1') {
      window.localStorage.setItem(STORAGE_KEY, '1')
    }
    if (params.get('eruda') === '0' || params.get('debugConsole') === '0') {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    /* ignore */
  }
}

/** Log helper visible in Eruda when the console is enabled. */
export function mobileDebugLog(...args: unknown[]): void {
  if (!isMobileDebugConsoleEnabled()) {
    return
  }
  console.info('[MG]', ...args)
}

function erudaScriptSrc(): string {
  const base = import.meta.env.BASE_URL || '/'
  const prefix = base.endsWith('/') ? base : `${base}/`
  return `${prefix}debug/eruda.js`
}

function loadErudaScript(): Promise<void> {
  if (window.eruda) {
    return Promise.resolve()
  }
  const existing = document.querySelector(`script[${ERUDA_SCRIPT_ATTR}]`)
  if (existing instanceof HTMLScriptElement) {
    return new Promise((resolve, reject) => {
      if (window.eruda) {
        resolve()
        return
      }
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener(
        'error',
        () => reject(new Error('Eruda script failed to load')),
        { once: true }
      )
    })
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = erudaScriptSrc()
    script.async = true
    script.setAttribute(ERUDA_SCRIPT_ATTR, '1')
    script.onload = () => resolve()
    script.onerror = () => reject(new Error(`Failed to load ${script.src}`))
    document.head.appendChild(script)
  })
}

/**
 * Dynamically load Eruda and show the floating green button.
 * Safe to call multiple times; no-op when disabled.
 */
export async function loadMobileDebugConsole(): Promise<void> {
  if (typeof window === 'undefined') {
    return
  }
  persistEnableFromQuery()
  if (!isMobileDebugConsoleEnabled() || loadStarted) {
    return
  }
  loadStarted = true
  try {
    await loadErudaScript()
    if (!window.eruda) {
      throw new Error('Eruda global missing after script load')
    }
    window.eruda.init()
    console.info(
      '[MG] Eruda ready — tap the floating button for Console. Disable: ?eruda=0'
    )
  } catch (err) {
    loadStarted = false
    console.warn('[MG] Failed to load Eruda:', err)
  }
}
