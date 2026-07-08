/**
 * Resolve `/static/…` URLs for dev playback of large binaries (case-square videos).
 *
 * Vite's `/static` proxy can gzip MP4 bodies without a matching Content-Encoding header,
 * which breaks HTML5 video. In dev, point media at the API origin directly.
 */
export function resolveDevStaticUrl(url: string | null | undefined): string | null {
  if (!url) return null
  const trimmed = url.trim()
  if (!trimmed) return null
  if (import.meta.env.PROD) return trimmed

  const devOrigin = typeof __DEV_API_ORIGIN__ === 'string' ? __DEV_API_ORIGIN__.trim() : ''
  if (!devOrigin || !trimmed.startsWith('/static/')) return trimmed

  return `${devOrigin.replace(/\/$/, '')}${trimmed}`
}
