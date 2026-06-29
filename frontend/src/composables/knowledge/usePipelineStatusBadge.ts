/**
 * Badge labels and Element Plus tag types for RAG/wiki pipeline states.
 */
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'

export type RagPipelineStatus = 'not_yet' | 'processing' | 'complete' | 'failed'
export type WikiPipelineStatus = 'disabled' | 'not_yet' | 'pending' | 'complete'

type BadgeType = 'success' | 'warning' | 'info' | 'danger'

export interface PipelineBadgeView {
  labelKey: string
  type: BadgeType
}

export function resolveRagStatus(document: KnowledgeDocument): RagPipelineStatus {
  if (document.rag_status) {
    return document.rag_status
  }
  switch (document.status) {
    case 'processing':
      return 'processing'
    case 'completed':
      return 'complete'
    case 'failed':
      return 'failed'
    default:
      return 'not_yet'
  }
}

export function resolveWikiStatus(document: KnowledgeDocument): WikiPipelineStatus {
  if (document.wiki_status) {
    return document.wiki_status
  }
  if (document.status !== 'completed') {
    return 'not_yet'
  }
  return 'pending'
}

export function ragBadgeView(status: RagPipelineStatus): PipelineBadgeView {
  switch (status) {
    case 'processing':
      return { labelKey: 'knowledge.pipelineBadge.rag.processing', type: 'warning' }
    case 'complete':
      return { labelKey: 'knowledge.pipelineBadge.rag.complete', type: 'success' }
    case 'failed':
      return { labelKey: 'knowledge.pipelineBadge.rag.failed', type: 'danger' }
    default:
      return { labelKey: 'knowledge.pipelineBadge.rag.notYet', type: 'info' }
  }
}

export function wikiBadgeView(status: WikiPipelineStatus): PipelineBadgeView {
  switch (status) {
    case 'disabled':
      return { labelKey: 'knowledge.pipelineBadge.wiki.disabled', type: 'info' }
    case 'pending':
      return { labelKey: 'knowledge.pipelineBadge.wiki.pending', type: 'warning' }
    case 'complete':
      return { labelKey: 'knowledge.pipelineBadge.wiki.complete', type: 'success' }
    default:
      return { labelKey: 'knowledge.pipelineBadge.wiki.notYet', type: 'info' }
  }
}

export function documentNeedsPipelinePoll(documents: KnowledgeDocument[]): boolean {
  return documents.some((doc) => {
    if (doc.status === 'processing' || doc.status === 'pending') {
      return true
    }
    return resolveWikiStatus(doc) === 'pending'
  })
}
