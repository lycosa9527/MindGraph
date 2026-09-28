/**
 * Coarse ZhiHui diagram-lesson banner / toast copy from job status + progress.
 * Keep labels light — detailed ops live in backend logs.
 */

export type ZhihuiDiagramTranslate = (
  key: string,
  params?: Record<string, string | number>
) => string

function asFiniteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function planningStage(progress: Record<string, unknown> | null | undefined): string {
  const raw = progress?.planning_stage
  return typeof raw === 'string' ? raw.trim().toLowerCase() : ''
}

export interface ZhihuiDiagramPhaseMessage {
  key: string
  params?: Record<string, number>
}

/**
 * Short banner / overlay label for the deck chrome.
 * Null when the status has no chrome copy.
 */
export function zhihuiDiagramPhaseMessage(
  status: string | null | undefined,
  progress: Record<string, unknown> | null | undefined
): ZhihuiDiagramPhaseMessage | null {
  const normalized = (status || '').trim()
  if (normalized === 'queued') {
    return { key: 'zhihui.diagram.phaseQueued' }
  }
  if (normalized === 'planning') {
    const stage = planningStage(progress)
    if (stage === 'develop') {
      const index = asFiniteNumber(progress?.branch_index)
      const total = asFiniteNumber(progress?.branch_total)
      if (index !== null && total !== null && total > 0) {
        return {
          key: 'zhihui.diagram.phasePlanningBranch',
          params: { current: index, total },
        }
      }
      return { key: 'zhihui.diagram.phasePlanningBranches' }
    }
    if (stage === 'close') {
      return { key: 'zhihui.diagram.phasePlanningClose' }
    }
    return { key: 'zhihui.diagram.phasePlanning' }
  }
  if (normalized === 'generating') {
    const slideCount = asFiniteNumber(progress?.slide_count)
    if (slideCount === null || slideCount <= 0) {
      return { key: 'zhihui.diagram.phaseGeneratingWait' }
    }
    return { key: 'zhihui.diagram.phaseGenerating' }
  }
  if (normalized === 'partial') {
    return { key: 'zhihui.diagram.phasePartial' }
  }
  if (normalized === 'failed') {
    return { key: 'zhihui.diagram.phaseFailed' }
  }
  if (normalized === 'complete' || normalized === 'ready') {
    return { key: 'zhihui.diagram.phaseComplete' }
  }
  if (normalized === 'cancelled') {
    return { key: 'zhihui.diagram.phaseCancelled' }
  }
  return null
}

/** String form of {@link zhihuiDiagramPhaseMessage} for callers that need one line. */
export function zhihuiDiagramPhaseLabel(
  status: string | null | undefined,
  progress: Record<string, unknown> | null | undefined,
  t: ZhihuiDiagramTranslate
): string {
  const message = zhihuiDiagramPhaseMessage(status, progress)
  if (!message) return ''
  return message.params ? String(t(message.key, message.params)) : String(t(message.key))
}

export type ZhihuiDiagramToastAnnouncement = {
  level: 'info' | 'success' | 'warning' | 'error'
  messageKey: string
  /** Prefer server error_message when present (failed). */
  useErrorMessage?: boolean
}

/**
 * Milestone toast for a status transition. Returns null when nothing should toast.
 */
export function zhihuiDiagramStatusToast(
  previousStatus: string | null | undefined,
  nextStatus: string | null | undefined
): ZhihuiDiagramToastAnnouncement | null {
  const prev = (previousStatus || '').trim()
  const next = (nextStatus || '').trim()
  if (!next || next === prev) {
    return null
  }
  if (next === 'planning' && (prev === 'queued' || prev === '')) {
    return { level: 'info', messageKey: 'zhihui.diagram.toastPlanning' }
  }
  if (next === 'generating' && (prev === 'planning' || prev === 'queued' || prev === '')) {
    return { level: 'info', messageKey: 'zhihui.diagram.toastGenerating' }
  }
  if (next === 'complete' || next === 'ready') {
    return { level: 'success', messageKey: 'zhihui.diagram.toastComplete' }
  }
  if (next === 'partial') {
    return { level: 'warning', messageKey: 'zhihui.diagram.toastPartial' }
  }
  if (next === 'failed') {
    return {
      level: 'error',
      messageKey: 'zhihui.diagram.phaseFailed',
      useErrorMessage: true,
    }
  }
  if (next === 'cancelled') {
    return { level: 'warning', messageKey: 'zhihui.diagram.toastCancelled' }
  }
  return null
}
