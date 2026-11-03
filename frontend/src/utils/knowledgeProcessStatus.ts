/**
 * Live personal-knowledge stage for the file panel.
 * Reads the document status the Celery worker stores while a folder is open.
 */

export interface KnowledgeProcessDoc {
  status: string
  file_name: string
  processing_progress?: string | null
}

export type KnowledgeProcessStage =
  | 'empty'
  | 'pending'
  | 'queued'
  | 'extracting'
  | 'cleaning'
  | 'splitting'
  | 'sending_oss'
  | 'embedding'
  | 'working'
  | 'ready'
  | 'failed'

/** Ordered worker stages. The panel prints the index as (1/7) … (7/7). */
const PROCESS_STEPS = [
  'pending',
  'queued',
  'extracting',
  'cleaning',
  'splitting',
  'sending_oss',
  'embedding',
] as const

const PROCESS_STEP_INDEX = new Map<string, number>(
  PROCESS_STEPS.map((step, index) => [step, index])
)

export interface KnowledgeProcessSnapshot {
  stage: KnowledgeProcessStage
  fileName: string
  count: number
}

function progressStage(doc: KnowledgeProcessDoc): KnowledgeProcessStage {
  if (doc.status === 'pending') return 'pending'
  const progress = doc.processing_progress?.trim() ?? ''
  if (progress === '') return 'queued'
  if (PROCESS_STEP_INDEX.has(progress)) return progress as KnowledgeProcessStage
  return 'working'
}

function stepIndex(stage: string): number | null {
  const index = PROCESS_STEP_INDEX.get(stage)
  return index === undefined ? null : index
}

/**
 * An unrecognized processing label sits after pending and before queued.
 * A named step still wins, and a waiting file does not hide work already running.
 */
const UNNAMED_RANK = 0.5

function stageRank(stage: KnowledgeProcessStage): number {
  return stepIndex(stage) ?? UNNAMED_RANK
}

function stepMark(stage: KnowledgeProcessStage): string {
  const index = stepIndex(stage)
  if (index === null) return ''
  return ` (${index + 1}/${PROCESS_STEPS.length})`
}

export function knowledgeProcessSnapshot(
  documents: KnowledgeProcessDoc[]
): KnowledgeProcessSnapshot {
  if (documents.length === 0) {
    return { stage: 'empty', fileName: '', count: 0 }
  }
  const working = documents.filter((doc) => doc.status === 'pending' || doc.status === 'processing')
  if (working.length === 0) {
    const failed = documents.filter((doc) => doc.status === 'failed')
    if (failed.length > 0) {
      const onlyFailed = failed.length === 1 ? failed[0] : undefined
      return {
        stage: 'failed',
        fileName: onlyFailed?.file_name ?? '',
        count: failed.length,
      }
    }
    return { stage: 'ready', fileName: '', count: documents.length }
  }
  const first = working[0]
  if (!first) {
    return { stage: 'empty', fileName: '', count: 0 }
  }
  let current = first
  let currentStage = progressStage(current)
  for (const doc of working.slice(1)) {
    const stage = progressStage(doc)
    if (stageRank(stage) > stageRank(currentStage)) {
      current = doc
      currentStage = stage
    }
  }
  return {
    stage: currentStage,
    fileName: working.length === 1 ? current.file_name : '',
    count: working.length,
  }
}

const STAGE_KEY: Record<KnowledgeProcessStage, string> = {
  empty: 'settings.knowledge.process.empty',
  pending: 'settings.knowledge.process.pending',
  queued: 'settings.knowledge.process.queued',
  extracting: 'settings.knowledge.process.extracting',
  cleaning: 'settings.knowledge.process.cleaning',
  splitting: 'settings.knowledge.process.splitting',
  sending_oss: 'settings.knowledge.process.sending_oss',
  embedding: 'settings.knowledge.process.embedding',
  working: 'settings.knowledge.process.working',
  ready: 'settings.knowledge.process.ready',
  failed: 'settings.knowledge.process.failed',
}

type ProcessTranslate = (key: string, named?: Record<string, string | number>) => string

/** One light status line: the furthest stage still running, or ready / failed. */
export function knowledgeProcessText(
  documents: KnowledgeProcessDoc[],
  translate: ProcessTranslate
): string {
  const snap = knowledgeProcessSnapshot(documents)
  const label = `${translate(STAGE_KEY[snap.stage])}${stepMark(snap.stage)}`
  if (snap.fileName) {
    return translate('settings.knowledge.process.withFile', { label, file: snap.fileName })
  }
  if (snap.count > 1 && snap.stage !== 'ready') {
    return translate('settings.knowledge.process.withCount', { label, count: snap.count })
  }
  return label
}
