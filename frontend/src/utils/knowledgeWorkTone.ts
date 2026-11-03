/**
 * Personal-knowledge work state shared by Settings and the canvas picker.
 * Blue while a file is still running, red when one failed, green when every file finished.
 */

export type KnowledgeWorkTone = 'idle' | 'working' | 'failed' | 'ready'

export function documentWorkTone(status: string): KnowledgeWorkTone {
  if (status === 'pending' || status === 'processing') return 'working'
  if (status === 'failed') return 'failed'
  if (status === 'completed') return 'ready'
  return 'idle'
}

export function folderWorkTone(folder: {
  document_count: number
  completed_count: number
  processing_count?: number
  failed_count?: number
}): KnowledgeWorkTone {
  const total = folder.document_count
  if (total <= 0) return 'idle'
  const failed = folder.failed_count ?? 0
  const processing = folder.processing_count ?? Math.max(0, total - folder.completed_count - failed)
  if (processing > 0) return 'working'
  if (failed > 0) return 'failed'
  if (folder.completed_count === total) return 'ready'
  return 'working'
}

export function folderIsReady(folder: {
  document_count: number
  completed_count: number
  processing_count?: number
  failed_count?: number
}): boolean {
  return folderWorkTone(folder) === 'ready'
}
