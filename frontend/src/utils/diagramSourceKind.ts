/**
 * Lite Document Summary: one markdown source family per diagram
 * (document upload/paste, web link, or voice notes).
 */
import { DOC_SUMMARY_PACKAGES_BASE } from '@/config/docSummaryApi'
import { apiRequestJson } from '@/utils/apiClient'

export type DiagramSourceKind = 'doc' | 'web' | 'voice'

type SourceKindDocument = {
  ingest_source?: string | null
  file_name?: string | null
  created_at?: string
}

type PackageDetailPayload = {
  documents?: SourceKindDocument[]
}

const DOC_INGEST_SOURCES = new Set(['upload', 'paste', 'file', 'document'])

export function diagramSourceKindFromIngest(
  ingest: string | null | undefined
): DiagramSourceKind | null {
  const kind = (ingest || '').trim()
  if (!kind) return null
  if (kind === 'web') return 'web'
  if (kind === 'voice_notes') return 'voice'
  if (DOC_INGEST_SOURCES.has(kind)) return 'doc'
  return 'doc'
}

export function diagramSourceKindFromDocument(
  document: SourceKindDocument
): DiagramSourceKind {
  const fromIngest = diagramSourceKindFromIngest(document.ingest_source)
  if (fromIngest) return fromIngest
  const name = (document.file_name || '').trim().toLowerCase()
  if (name.startsWith('voice recording') || name.startsWith('voice_recording')) {
    return 'voice'
  }
  if (name.startsWith('http://') || name.startsWith('https://')) {
    return 'web'
  }
  return 'doc'
}

/** Oldest source wins so a later voice live-save cannot steal a document diagram. */
export function resolveLockedSourceKind(
  documents: ReadonlyArray<SourceKindDocument>
): DiagramSourceKind | null {
  if (documents.length === 0) return null
  const oldest = documents.reduce((current, candidate) => {
    const currentAt = current.created_at || ''
    const candidateAt = candidate.created_at || ''
    if (!currentAt) return candidate
    if (!candidateAt) return current
    return candidateAt < currentAt ? candidate : current
  })
  return diagramSourceKindFromDocument(oldest)
}

export function isDiagramSourceKindLocked(
  locked: DiagramSourceKind | null,
  requested: DiagramSourceKind
): boolean {
  return locked !== null && locked !== requested
}

export function diagramSourceLockMessage(
  translate: (key: string, named?: Record<string, string>) => string,
  locked: DiagramSourceKind
): string {
  return translate('canvas.ribbon.sourceLocked', {
    source: translate(`canvas.ribbon.sourceKind.${locked}`),
  })
}

export async function fetchLockedDiagramSourceKind(
  packageId: number
): Promise<DiagramSourceKind | null> {
  const detail = await apiRequestJson<PackageDetailPayload>(
    `${DOC_SUMMARY_PACKAGES_BASE}/${packageId}`
  )
  return resolveLockedSourceKind(detail.documents ?? [])
}
