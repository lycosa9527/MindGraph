import { describe, expect, it } from 'vitest'

import {
  zhihuiDiagramPhaseLabel,
  zhihuiDiagramStatusToast,
} from '../src/components/zhihui/zhihuiDiagramProgress'

function t(key: string, params?: Record<string, string | number>): string {
  if (!params) return key
  return `${key}:${Object.entries(params)
    .map(([name, value]) => `${name}=${value}`)
    .join(',')}`
}

describe('zhihuiDiagramPhaseLabel', () => {
  it('uses light planning stage labels', () => {
    expect(zhihuiDiagramPhaseLabel('planning', { planning_stage: 'open' }, t)).toBe(
      'zhihui.diagram.phasePlanning'
    )
    expect(
      zhihuiDiagramPhaseLabel(
        'planning',
        { planning_stage: 'develop', branch_index: 2, branch_total: 5 },
        t
      )
    ).toBe('zhihui.diagram.phasePlanningBranch:current=2,total=5')
    expect(zhihuiDiagramPhaseLabel('planning', { planning_stage: 'close' }, t)).toBe(
      'zhihui.diagram.phasePlanningClose'
    )
  })

  it('distinguishes waiting vs drawing while generating', () => {
    expect(zhihuiDiagramPhaseLabel('generating', { slide_count: 0 }, t)).toBe(
      'zhihui.diagram.phaseGeneratingWait'
    )
    expect(zhihuiDiagramPhaseLabel('generating', { slide_count: 3 }, t)).toBe(
      'zhihui.diagram.phaseGenerating'
    )
  })
})

describe('zhihuiDiagramStatusToast', () => {
  it('announces coarse milestones only', () => {
    expect(zhihuiDiagramStatusToast('queued', 'planning')).toEqual({
      level: 'info',
      messageKey: 'zhihui.diagram.toastPlanning',
    })
    expect(zhihuiDiagramStatusToast('planning', 'generating')).toEqual({
      level: 'info',
      messageKey: 'zhihui.diagram.toastGenerating',
    })
    expect(zhihuiDiagramStatusToast('generating', 'complete')).toEqual({
      level: 'success',
      messageKey: 'zhihui.diagram.toastComplete',
    })
    expect(zhihuiDiagramStatusToast('generating', 'failed')).toEqual({
      level: 'error',
      messageKey: 'zhihui.diagram.phaseFailed',
      useErrorMessage: true,
    })
    expect(zhihuiDiagramStatusToast('generating', 'generating')).toBeNull()
    expect(zhihuiDiagramStatusToast('planning', 'develop')).toBeNull()
  })
})
