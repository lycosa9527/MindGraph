/**
 * Save a seminar generate_dingtalk preview into the signed-in user's library.
 */
import { authFetch } from '@/utils/api'

export type CollabDiagramSaveFailure = 'full' | 'missing' | 'denied' | 'failed'

export type CollabDiagramSaveResult =
  { ok: true; diagramId: string } | { ok: false; reason: CollabDiagramSaveFailure }

export function collabDiagramSaveFailureKey(reason: CollabDiagramSaveFailure): string {
  if (reason === 'full') {
    return 'mindmate.diagramLibraryFull'
  }
  if (reason === 'missing') {
    return 'mindmate.openCanvasSaveRetry'
  }
  return 'mindmate.openCanvasFailed'
}

export function collabDiagramSaveFailureFromResponse(
  status: number,
  detail: string
): CollabDiagramSaveFailure {
  if (detail === 'limit_reached') {
    return 'full'
  }
  if (status === 403) {
    return 'denied'
  }
  if (status === 404 || detail === 'no_spec' || detail === 'not_found') {
    return 'missing'
  }
  return 'failed'
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown }
    return typeof data.detail === 'string' ? data.detail : ''
  } catch {
    return ''
  }
}

export type SharedCanvasDiagramPreview = {
  diagramId: string
  title: string
  diagramType: string
  spec: Record<string, unknown>
}

export async function fetchSharedCanvasDiagramPreview(
  sessionId: string,
  diagramId: string
): Promise<SharedCanvasDiagramPreview | null> {
  const session = sessionId.trim()
  const diagram = diagramId.trim()
  if (!session || !diagram) {
    return null
  }
  try {
    const response = await authFetch(
      `/api/mindmate/seminar/${encodeURIComponent(session)}/canvas-diagram/${encodeURIComponent(diagram)}`
    )
    if (!response.ok) {
      return null
    }
    const data = (await response.json()) as {
      diagram_id?: string
      title?: string
      diagram_type?: string
      spec?: unknown
    }
    if (!data.spec || typeof data.spec !== 'object' || Array.isArray(data.spec)) {
      return null
    }
    return {
      diagramId: data.diagram_id?.trim() || diagram,
      title: data.title?.trim() || '',
      diagramType: data.diagram_type?.trim() || 'mind_map',
      spec: data.spec as Record<string, unknown>,
    }
  } catch {
    return null
  }
}

export async function saveSharedCanvasDiagram(
  sessionId: string,
  diagramId: string
): Promise<CollabDiagramSaveResult> {
  const session = sessionId.trim()
  const diagram = diagramId.trim()
  if (!session || !diagram) {
    return { ok: false, reason: 'missing' }
  }
  try {
    const response = await authFetch(
      `/api/mindmate/seminar/${encodeURIComponent(session)}/canvas-diagram`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ diagram_id: diagram }),
      }
    )
    if (!response.ok) {
      const detail = await readErrorDetail(response)
      return { ok: false, reason: collabDiagramSaveFailureFromResponse(response.status, detail) }
    }
    const data = (await response.json()) as { diagram_id?: string }
    const savedId = data.diagram_id?.trim()
    if (!savedId) {
      return { ok: false, reason: 'failed' }
    }
    return { ok: true, diagramId: savedId }
  } catch {
    return { ok: false, reason: 'failed' }
  }
}

export async function saveCollabDiagramToLibrary(
  sessionId: string,
  previewId: string
): Promise<CollabDiagramSaveResult> {
  const session = sessionId.trim()
  const preview = previewId.trim()
  if (!session || !preview) {
    return { ok: false, reason: 'missing' }
  }
  try {
    const response = await authFetch(
      `/api/mindmate/seminar/${encodeURIComponent(session)}/diagram-library`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preview_id: preview }),
      }
    )
    if (!response.ok) {
      const detail = await readErrorDetail(response)
      return { ok: false, reason: collabDiagramSaveFailureFromResponse(response.status, detail) }
    }
    const data = (await response.json()) as { diagram_id?: string }
    const diagramId = data.diagram_id?.trim()
    if (!diagramId) {
      return { ok: false, reason: 'failed' }
    }
    return { ok: true, diagramId }
  } catch {
    return { ok: false, reason: 'failed' }
  }
}
