/**
 * Document Summary lite: save pending draft (file / paste / URL) then generate.
 */
import { type Ref } from 'vue'

import type { usePackageDetail } from '@/composables/fileCenter/useFileCenter'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'

type PackageDetailQuery = ReturnType<typeof usePackageDetail>

const POLL_MS = 500
const WAIT_READY_MS = 120_000
/** Backend / browser URL length ceiling for web ingest. */
export const DOC_SUMMARY_WEB_URL_MAX_CHARS = 2000

export type LiteDraftKind = 'none' | 'file' | 'paste' | 'web'

export function isValidDocSummaryWebUrl(url: string): boolean {
  const trimmed = url.trim()
  if (!trimmed || trimmed.length > DOC_SUMMARY_WEB_URL_MAX_CHARS) return false
  try {
    const parsed = new URL(trimmed)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

export function resolveLiteDraftKind(options: {
  hasActiveSource: boolean
  activeTab: string
  uploadedFile: File | null
  pastedText: string
  webUrl: string
}): LiteDraftKind {
  if (options.hasActiveSource) return 'none'
  if (options.activeTab === 'file') {
    if (options.uploadedFile) return 'file'
    if (options.pastedText.trim()) return 'paste'
    return 'none'
  }
  if (options.activeTab === 'web' && isValidDocSummaryWebUrl(options.webUrl)) return 'web'
  return 'none'
}

export async function waitForDocSummarySourceReady(options: {
  detailQuery: PackageDetailQuery
  documents: Ref<KnowledgeDocument[]>
  timeoutMs?: number
}): Promise<'completed' | 'failed' | 'timeout'> {
  const timeoutMs = options.timeoutMs ?? WAIT_READY_MS
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    await options.detailQuery.refetch()
    const docs = options.documents.value
    if (docs.length === 0) return 'failed'
    const doc = docs[0]
    if (doc?.status === 'completed') return 'completed'
    if (doc?.status === 'failed') return 'failed'
    await new Promise((resolve) => {
      window.setTimeout(resolve, POLL_MS)
    })
  }
  return 'timeout'
}
