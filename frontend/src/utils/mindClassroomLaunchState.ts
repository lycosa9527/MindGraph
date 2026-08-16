/**
 * Launch-button lock and status labels for 思维讲堂 prep.
 */
import type { MindClassroomPresentationId } from '@/config/mindClassroom'

export function isMindClassroomQueueBusy(
  jobStatus: string | null | undefined,
  starting = false
): boolean {
  if (starting) return true
  return jobStatus === 'queued' || jobStatus === 'planning' || jobStatus === 'generating'
}

export function mindClassroomStartLabelKey(options: {
  jobStatus: string | null | undefined
  starting?: boolean
  hasPrepared?: boolean
  presentation?: MindClassroomPresentationId
}): string {
  const status = options.jobStatus
  if (isMindClassroomQueueBusy(status, options.starting)) {
    if (status === 'planning') return 'canvas.mindClassroom.queue.planning'
    if (status === 'generating') {
      return options.presentation === 'slide_deck'
        ? 'canvas.mindClassroom.queue.generating'
        : 'canvas.mindClassroom.queue.transcript'
    }
    if (status === 'queued') return 'canvas.mindClassroom.queue.queued'
    return 'canvas.mindClassroom.queue.preparing'
  }
  if (options.hasPrepared) return 'canvas.mindClassroom.queue.ready'
  if (status === 'failed') return 'canvas.mindClassroom.queue.failed'
  return 'canvas.mindClassroom.start'
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
