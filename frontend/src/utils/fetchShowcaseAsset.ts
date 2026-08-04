/**
 * Fetch Showcase asset bytes for in-app readers (pdf.js / docx-preview).
 *
 * AuthZ URLs are same-origin `/api/showcase/assets/...`. With COS enabled the
 * default response is a 302 to a cross-origin presigned GET — credentialed
 * `fetch` then fails CORS (while ``<img>`` thumbnails still paint). Append
 * ``proxy=1`` so the API streams bytes after AuthZ (no browser→COS hop).
 */

function withQuery(url: string, key: string, value: string): string {
  const parsed = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://local')
  parsed.searchParams.set(key, value)
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return parsed.toString()
  }
  return `${parsed.pathname}${parsed.search}${parsed.hash}`
}

export function withShowcaseAssetProxy(url: string): string {
  return withQuery(url, 'proxy', '1')
}

export async function fetchShowcaseAsset(
  url: string,
  init: RequestInit & { cacheBust?: boolean } = {}
): Promise<Response> {
  const { cacheBust = true, ...rest } = init
  let target = withShowcaseAssetProxy(url)
  if (cacheBust) {
    target = withQuery(target, 'mg_preview', String(Date.now()))
  }
  return fetch(target, {
    credentials: 'same-origin',
    cache: 'no-store',
    ...rest,
  })
}
