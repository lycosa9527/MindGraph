/** Resolve MindMate generate_dingtalk preview PNGs (IndexedDB → temp URL → library re-render). */

import { authFetch } from '@/utils/api'
import {
  extractFirstMarkdownImageUrl,
  parseMindmateDiagramLibraryId,
} from '@/utils/mindmateDiagramMeta'
import {
  extractMindmatePreviewCacheKey,
  readMindmateDiagramPreview,
  writeMindmateDiagramPreview,
} from '@/utils/mindmateDiagramPreviewCache'

const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47] as const

function resolveFetchUrl(imageUrl: string): string {
  if (/^https?:\/\//i.test(imageUrl)) {
    return imageUrl
  }
  if (typeof window === 'undefined') {
    return imageUrl
  }
  const path = imageUrl.startsWith('/') ? imageUrl : `/${imageUrl}`
  return `${window.location.origin}${path}`
}

async function isPngBlob(blob: Blob): Promise<boolean> {
  if (blob.size < 4) {
    return false
  }
  if (blob.type && blob.type !== 'image/png') {
    return false
  }
  const bytes = new Uint8Array(await blob.slice(0, 4).arrayBuffer())
  return PNG_SIGNATURE.every((byte, index) => bytes[index] === byte)
}

async function fetchPreviewBlob(imageUrl: string): Promise<Blob | null> {
  try {
    const response = await fetch(resolveFetchUrl(imageUrl), { credentials: 'same-origin' })
    if (!response.ok) {
      return null
    }
    const blob = await response.blob()
    if (!(await isPngBlob(blob))) {
      return null
    }
    return blob
  } catch {
    return null
  }
}

async function fetchLibraryDiagramPreviewBlob(libraryDiagramId: string): Promise<Blob | null> {
  try {
    const response = await authFetch(
      `/api/diagrams/${encodeURIComponent(libraryDiagramId)}/png`
    )
    if (!response.ok) {
      return null
    }
    const data = (await response.json()) as { url?: string }
    const pngUrl = data.url?.trim()
    if (!pngUrl) {
      return null
    }
    return fetchPreviewBlob(pngUrl)
  } catch {
    return null
  }
}

export interface ResolveMindmateDiagramPreviewOptions {
  content: string
  pageHost?: string
  libraryDiagramId?: string | null
  /** When true (default), store successful fetches in IndexedDB. */
  persist?: boolean
}

/**
 * Load a diagram preview PNG: local cache first, then live temp URL, then library re-render.
 */
export async function resolveMindmateDiagramPreviewBlob(
  options: ResolveMindmateDiagramPreviewOptions
): Promise<Blob | null> {
  const cacheKey = extractMindmatePreviewCacheKey(options.content)
  if (!cacheKey) {
    return null
  }

  const cached = await readMindmateDiagramPreview(cacheKey)
  if (cached) {
    return cached
  }

  const persist = options.persist !== false
  const imageUrl = extractFirstMarkdownImageUrl(options.content, options.pageHost)
  if (imageUrl) {
    const blob = await fetchPreviewBlob(imageUrl)
    if (blob) {
      if (persist) {
        await writeMindmateDiagramPreview(cacheKey, blob)
      }
      return blob
    }
  }

  const libraryId =
    options.libraryDiagramId?.trim() ||
    parseMindmateDiagramLibraryId(options.content)
  if (libraryId) {
    const libraryBlob = await fetchLibraryDiagramPreviewBlob(libraryId)
    if (libraryBlob) {
      if (persist) {
        await writeMindmateDiagramPreview(cacheKey, libraryBlob)
      }
      return libraryBlob
    }
  }

  return null
}
