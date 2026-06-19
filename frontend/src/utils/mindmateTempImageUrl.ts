/** Rewrite MindMate temp-image markdown URLs for same-origin dev proxy. */

const TEMP_IMAGE_ABSOLUTE_URL_RE =
  /https?:\/\/[^/]+\/(?:api\/)?temp_images\/([^\s)"'<>]+)/gi

/**
 * Remote MindGraph hosts proxied through `/api/proxy-image` (must match backend whitelist).
 * Keeps `<img>` loads same-origin and avoids CORB on HTML/JSON error bodies from cross-origin fetches.
 */
export const MINDMATE_TEMP_IMAGE_PROXY_HOSTS = new Set(['mg.mindspringedu.com'])

function isLoopbackHost(hostname: string): boolean {
  const host = (hostname || '').toLowerCase()
  if (host === 'localhost' || host === '127.0.0.1' || host === '::1') {
    return true
  }
  if (host.startsWith('127.')) {
    const parts = host.split('.')
    return (
      parts.length === 4 &&
      parts.every((part) => {
        if (!part.length || !/^\d+$/.test(part)) {
          return false
        }
        const n = Number(part)
        return n >= 0 && n <= 255
      })
    )
  }
  return false
}

/** True when the temp-image URL should be rewritten to `/api/temp_images/...`. */
export function shouldRewriteMindmateTempImageUrl(url: URL, pageHost?: string): boolean {
  if (isLoopbackHost(url.hostname)) {
    return true
  }
  const page = (pageHost || '').trim().toLowerCase()
  if (!page) {
    return false
  }
  return url.host.toLowerCase() === page
}

function isLoopbackPageHost(pageHost?: string): boolean {
  if (!pageHost) {
    return false
  }
  return isLoopbackHost(pageHost.split(':')[0])
}

/** True when the URL should load via same-origin `/api/proxy-image`. */
export function shouldProxyMindmateTempImageUrl(url: URL, pageHost?: string): boolean {
  if (shouldRewriteMindmateTempImageUrl(url, pageHost)) {
    return false
  }
  if (MINDMATE_TEMP_IMAGE_PROXY_HOSTS.has(url.hostname.toLowerCase())) {
    return true
  }
  // Local Vite dev (:41732): avoid cross-origin <img> (CORB) — proxy via local API.
  if (isLoopbackPageHost(pageHost) && (url.pathname || '').includes('/temp_images/')) {
    return true
  }
  return false
}

/**
 * Rewrite temp-image markdown URLs for MindMate display.
 *
 * - Loopback / same-page host → `/api/temp_images/...` (Vite → local :9527 in dev)
 * - Local dev UI + other hosts → `/api/proxy-image?url=...` (same-origin, avoids CORB)
 * - Production same-origin host → `/api/temp_images/...`
 */
export function rewriteMindmateTempImageUrls(content: string, pageHost?: string): string {
  return (content || '').replace(TEMP_IMAGE_ABSOLUTE_URL_RE, (match, pathAndQuery: string) => {
    try {
      const parsed = new URL(match)
      if (shouldRewriteMindmateTempImageUrl(parsed, pageHost)) {
        return `/api/temp_images/${pathAndQuery}`
      }
      if (shouldProxyMindmateTempImageUrl(parsed, pageHost)) {
        return `/api/proxy-image?url=${encodeURIComponent(match)}`
      }
    } catch {
      return match
    }
    return match
  })
}
