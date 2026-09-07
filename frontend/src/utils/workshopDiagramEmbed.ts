/**
 * Insert a personal-library diagram into 研习社 as markdown.
 *
 * The server renders the PNG and stores it on COS (local disk fallback).
 * Compose only inserts ``![mg:{id}](/api/chat/attachments/{id}/download)``.
 * Viewers load that URL and follow the COS redirect.
 */
import { apiPost } from '@/utils/apiClient'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export interface WorkshopDiagramEmbedSource {
  id: string
  title: string
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

export async function embedWorkshopLibraryDiagram(
  diagram: WorkshopDiagramEmbedSource
): Promise<string | null> {
  const res = await apiPost(`/api/chat/library-diagrams/${encodeURIComponent(diagram.id)}`)
  if (!res.ok) {
    return null
  }
  const data = (await res.json()) as { file_path?: string; filename?: string }
  if (!data.file_path) {
    return null
  }
  return buildWorkshopDiagramMarkdown(diagram.id, diagram.title, data.file_path)
}
