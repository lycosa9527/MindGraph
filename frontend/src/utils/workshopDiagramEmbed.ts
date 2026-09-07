/**
 * Insert a personal-library diagram into 研习社 as a durable chat image.
 *
 * Signed GET /api/diagrams/{id}/png URLs expire. Upload the rendered PNG
 * through /api/chat/upload so message markdown keeps working.
 */
import { apiUpload } from '@/utils/apiClient'
import { sameOriginTempImageFetchUrl } from '@/utils/mindmateTempImageUrl'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export interface WorkshopDiagramEmbedSource {
  id: string
  title: string
  thumbnail: string | null
}

export interface WorkshopDiagramUploadResult {
  file_path: string
  filename: string
}

export function buildWorkshopDiagramMarkdown(
  diagramId: string,
  title: string,
  filePath: string
): string {
  const id = diagramId.trim()
  const safeTitle = title.replace(/[[\]]/g, '').trim() || 'diagram'
  const alt = UUID_RE.test(id) ? `mg:${id}` : safeTitle
  const comment = UUID_RE.test(id) ? `\n<!-- mg-diagram-id:${id} -->` : ''
  return `![${alt}](${filePath})${comment}`
}

function decodeDataUrlToBlob(dataUrl: string): Blob | null {
  const trimmed = dataUrl.trim()
  if (!trimmed) {
    return null
  }
  const match = trimmed.match(/^data:([^;,]+)?(;base64)?,(.*)$/s)
  if (!match) {
    if (/^[A-Za-z0-9+/=\s]+$/.test(trimmed) && trimmed.length > 64) {
      try {
        const binary = atob(trimmed.replace(/\s/g, ''))
        const bytes = new Uint8Array(binary.length)
        for (let i = 0; i < binary.length; i += 1) {
          bytes[i] = binary.charCodeAt(i)
        }
        return new Blob([bytes], { type: 'image/png' })
      } catch {
        return null
      }
    }
    return null
  }
  try {
    const mime = match[1]?.trim() || 'image/png'
    const payload = match[3] ?? ''
    const binary = match[2] ? atob(payload) : decodeURIComponent(payload)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i)
    }
    return new Blob([bytes], { type: mime })
  } catch {
    return null
  }
}

export async function blobFromDiagramThumbnail(thumbnail: string | null): Promise<Blob | null> {
  if (!thumbnail) {
    return null
  }
  const fromData = decodeDataUrlToBlob(thumbnail)
  if (fromData && fromData.size > 64) {
    return fromData
  }
  if (thumbnail.startsWith('/') || /^https?:\/\//i.test(thumbnail)) {
    try {
      const res = await fetch(thumbnail, { credentials: 'include', cache: 'no-store' })
      if (res.ok) {
        const blob = await res.blob()
        return blob.size > 64 ? blob : null
      }
    } catch {
      return null
    }
  }
  return null
}

export async function fetchDiagramPngBlob(diagramId: string): Promise<Blob | null> {
  const res = await fetch(`/api/diagrams/${encodeURIComponent(diagramId)}/png`, {
    credentials: 'include',
  })
  if (!res.ok) {
    return null
  }
  const data = (await res.json()) as { url?: string }
  if (!data.url) {
    return null
  }
  const imgRes = await fetch(sameOriginTempImageFetchUrl(data.url), {
    credentials: 'include',
    cache: 'no-store',
  })
  if (!imgRes.ok) {
    return null
  }
  const blob = await imgRes.blob()
  return blob.size > 64 ? blob : null
}

export async function resolveWorkshopDiagramPngBlob(
  diagram: WorkshopDiagramEmbedSource
): Promise<Blob | null> {
  try {
    const rendered = await fetchDiagramPngBlob(diagram.id)
    if (rendered) {
      return rendered
    }
  } catch {
    // fall through to library thumbnail
  }
  return blobFromDiagramThumbnail(diagram.thumbnail)
}

function safePngFilename(title: string): string {
  const base = title.replace(/[^\p{L}\p{N}_-]+/gu, '_').replace(/^_+|_+$/g, '')
  const clipped = (base || 'diagram').slice(0, 80)
  return `${clipped}.png`
}

export async function uploadWorkshopChatImage(
  blob: Blob,
  filename: string
): Promise<WorkshopDiagramUploadResult | null> {
  const formData = new FormData()
  formData.append('file', blob, filename)
  const res = await apiUpload('/api/chat/upload', formData)
  if (!res.ok) {
    return null
  }
  const data = (await res.json()) as { file_path?: string; filename?: string }
  if (!data.file_path) {
    return null
  }
  return {
    file_path: data.file_path,
    filename: data.filename || filename,
  }
}

export async function embedWorkshopLibraryDiagram(
  diagram: WorkshopDiagramEmbedSource
): Promise<string | null> {
  const blob = await resolveWorkshopDiagramPngBlob(diagram)
  if (!blob) {
    return null
  }
  const uploaded = await uploadWorkshopChatImage(blob, safePngFilename(diagram.title))
  if (!uploaded) {
    return null
  }
  return buildWorkshopDiagramMarkdown(diagram.id, diagram.title, uploaded.file_path)
}
