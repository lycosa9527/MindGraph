/** Rewrite MindMate temp-image markdown URLs for same-origin dev proxy. */

import {
  CANONICAL_PUBLIC_HOST,
  FIRST_PARTY_PUBLIC_HOSTS,
  LEGACY_PUBLIC_HOST,
} from '@/constants/publicHosts'

const TEMP_IMAGE_ABSOLUTE_URL_RE = /https?:\/\/[^/]+\/(?:api\/)?temp_images\/([^\s)"'<>]+)/gi

/**
 * Remote MindGraph hosts proxied through `/api/proxy-image` (must match backend whitelist).
 * Keeps `<img>` loads same-origin and avoids CORB on HTML/JSON error bodies from cross-origin fetches.
 * ``www`` and legacy ``mg`` are the same app.
 */
export const MINDMATE_TEMP_IMAGE_PROXY_HOSTS = FIRST_PARTY_PUBLIC_HOSTS

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

/** Public hosts load over https. The legacy mg host is emitted as www. Loopback stays. */
function publicHttpsTempImageUrl(url: URL): URL {
  const next = new URL(url.href)
  if (next.protocol === 'http:' && !isLoopbackHost(next.hostname)) {
    next.protocol = 'https:'
    if (next.port === '80') {
      next.port = ''
    }
  }
  if (next.hostname.toLowerCase() === LEGACY_PUBLIC_HOST) {
    next.hostname = CANONICAL_PUBLIC_HOST
    next.protocol = 'https:'
    if (next.port === '80' || next.port === '443') {
      next.port = ''
    }
  }
  return next
}

/** Public absolute URL with https. Loopback and relative paths stay as given. */
export function toPublicHttpsUrl(rawUrl: string): string {
  const trimmed = (rawUrl || '').trim()
  if (!trimmed.toLowerCase().startsWith('http://')) {
    return trimmed
  }
  try {
    return publicHttpsTempImageUrl(new URL(trimmed)).href
  } catch {
    return trimmed
  }
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
  if (url.host.toLowerCase() === page) {
    return true
  }
  const pageName = page.split(':')[0]
  return (
    FIRST_PARTY_PUBLIC_HOSTS.has(url.hostname.toLowerCase()) &&
    FIRST_PARTY_PUBLIC_HOSTS.has(pageName)
  )
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
 * Follow-up fetch for a PNG we just rendered on this API.
 *
 * ``GET /api/diagrams/{id}/png`` may still return ``EXTERNAL_BASE_URL``
 * (test/prod). That host is the wrong disk in local Vite, and CSP blocks it.
 * Always load ``/api/temp_images/...`` on the page origin (Vite → :9527).
 */
export function sameOriginTempImageFetchUrl(rawUrl: string): string {
  const trimmed = (rawUrl || '').trim()
  if (!trimmed) {
    return trimmed
  }
  try {
    const parsed = new URL(trimmed, 'http://localhost')
    const marker = '/temp_images/'
    const idx = parsed.pathname.indexOf(marker)
    if (idx === -1) {
      return trimmed
    }
    const rest = parsed.pathname.slice(idx + marker.length)
    return `/api/temp_images/${rest}${parsed.search}`
  } catch {
    return trimmed
  }
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
      const parsed = publicHttpsTempImageUrl(new URL(match))
      if (shouldRewriteMindmateTempImageUrl(parsed, pageHost)) {
        return `/api/temp_images/${pathAndQuery}`
      }
      if (shouldProxyMindmateTempImageUrl(parsed, pageHost)) {
        return `/api/proxy-image?url=${encodeURIComponent(parsed.href)}`
      }
      return parsed.href
    } catch {
      return match
    }
  })
}
