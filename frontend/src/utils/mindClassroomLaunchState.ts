/**
 * Launch-button lock and status labels for 思维讲堂 prep.
 */
import type { MindClassroomPresentationId } from '@/config/mindClassroom'

export type MindClassroomProgressStats = {
  branchName: string
  ttsReady: boolean
  done: number
  total: number
  inFlight: number
}

export function isMindClassroomQueueBusy(
  jobStatus: string | null | undefined,
  starting = false,
  voiceWarmup?: string | null
): boolean {
  if (starting) return true
  if (voiceWarmup === 'loading') return true
  return jobStatus === 'queued' || jobStatus === 'planning' || jobStatus === 'generating'
}

const BRANCH_NAME_MAX = 16

export function mindClassroomProgressStats(
  progress: Record<string, unknown> | null | undefined
): MindClassroomProgressStats {
  const slots = progressBranchSlots(progress)
  const done = countByState(progress, slots, 'done')
  const total = progressTotal(progress, slots)
  const inFlight = total > 0 ? Math.max(0, total - done) : progressInt(progress, 'in_flight')
  return {
    branchName: mindClassroomProgressBranchName(progress),
    ttsReady: progress?.tts_ready === true,
    done,
    total,
    inFlight,
  }
}

export function mindClassroomProgressBranchName(
  progress: Record<string, unknown> | null | undefined
): string {
  if (!progress) return ''
  const fromSlots = branchNameFromSlots(progressBranchSlots(progress))
  if (fromSlots) return fromSlots
  const direct = progress.branch_label
  if (typeof direct === 'string' && direct.trim()) {
    return clipBranchName(direct)
  }
  const labels = progress.branch_labels
  if (Array.isArray(labels)) {
    for (const item of labels) {
      if (typeof item === 'string' && item.trim()) {
        return clipBranchName(item)
      }
    }
  }
  return ''
}

function progressBranchSlots(
  progress: Record<string, unknown> | null | undefined
): Array<Record<string, unknown>> {
  const raw = progress?.branches
  if (!Array.isArray(raw)) return []
  return raw.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
}

function branchNameFromSlots(slots: Array<Record<string, unknown>>): string {
  for (const wanted of ['streaming', 'pending'] as const) {
    for (const slot of slots) {
      if (slot.state !== wanted) continue
      const label = slot.label
      if (typeof label === 'string' && label.trim()) {
        return clipBranchName(label)
      }
    }
  }
  return ''
}

function progressInt(progress: Record<string, unknown> | null | undefined, key: string): number {
  const value = progress?.[key]
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? Math.floor(value) : 0
}

function progressTotal(
  progress: Record<string, unknown> | null | undefined,
  slots: Array<Record<string, unknown>>
): number {
  if (slots.length) return slots.length
  return progressInt(progress, 'branch_total')
}

function countByState(
  progress: Record<string, unknown> | null | undefined,
  slots: Array<Record<string, unknown>>,
  state: string
): number {
  if (slots.length) {
    return slots.filter((slot) => slot.state === state).length
  }
  return progressInt(progress, 'done')
}

function clipBranchName(raw: string): string {
  const text = raw.trim()
  if (text.length <= BRANCH_NAME_MAX) return text
  return `${[...text].slice(0, BRANCH_NAME_MAX).join('')}…`
}

export function mindClassroomStartFillPercent(done: number, total: number): number {
  if (!Number.isFinite(total) || total <= 0) return 0
  if (!Number.isFinite(done) || done <= 0) return 0
  return Math.min(100, Math.round((done / total) * 100))
}

export function mindClassroomStartLabelKey(options: {
  jobStatus: string | null | undefined
  starting?: boolean
  hasPrepared?: boolean
  presentation?: MindClassroomPresentationId
  voiceWarmup?: string | null
  branchName?: string | null
  ttsReady?: boolean
  remaining?: number
}): string {
  const status = options.jobStatus
  const jobBusy =
    options.starting === true ||
    status === 'queued' ||
    status === 'planning' ||
    status === 'generating'
  if (jobBusy) {
    if (status === 'planning') return 'canvas.mindClassroom.queue.planning'
    if (status === 'queued') return 'canvas.mindClassroom.queue.queued'
    if (status === 'generating' || scriptsStillWriting(status, options.remaining)) {
      return generatingStartLabelKey(options)
    }
    if (waitingForVoice(options)) return 'canvas.mindClassroom.queue.loadingVoice'
    return 'canvas.mindClassroom.queue.preparing'
  }
  if (waitingForVoice(options)) {
    return 'canvas.mindClassroom.queue.loadingVoice'
  }
  if (options.hasPrepared) return 'canvas.mindClassroom.queue.ready'
  if (status === 'failed') return 'canvas.mindClassroom.queue.failed'
  return 'canvas.mindClassroom.start'
}

function scriptsStillWriting(
  status: string | null | undefined,
  remaining: number | undefined
): boolean {
  if (typeof remaining === 'number') return remaining > 0
  return status === 'generating'
}

function waitingForVoice(options: {
  hasPrepared?: boolean
  voiceWarmup?: string | null
}): boolean {
  return options.hasPrepared === true && options.voiceWarmup === 'loading'
}

function generatingStartLabelKey(options: {
  jobStatus?: string | null
  presentation?: MindClassroomPresentationId
  voiceWarmup?: string | null
  branchName?: string | null
  hasPrepared?: boolean
  ttsReady?: boolean
  remaining?: number
}): string {
  if (options.presentation === 'slide_deck') {
    return 'canvas.mindClassroom.queue.generating'
  }
  if (scriptsStillWriting(options.jobStatus, options.remaining)) {
    if (options.ttsReady && (options.remaining ?? 0) > 0) {
      return 'canvas.mindClassroom.queue.transcriptRemaining'
    }
    if (options.branchName?.trim()) {
      return 'canvas.mindClassroom.queue.transcriptBranch'
    }
    return 'canvas.mindClassroom.queue.transcript'
  }
  if (waitingForVoice(options)) {
    return 'canvas.mindClassroom.queue.loadingVoice'
  }
  return 'canvas.mindClassroom.queue.transcript'
}

export function shouldShowMindClassroomRestart(options: {
  jobStatus: string | null | undefined
  hasPrepared?: boolean
  authenticated?: boolean
}): boolean {
  if (options.authenticated === false) return false
  if (options.hasPrepared) return true
  const status = options.jobStatus
  return (
    status === 'queued' ||
    status === 'planning' ||
    status === 'generating' ||
    status === 'failed' ||
    status === 'ready' ||
    status === 'partial'
  )
}
