import { describe, expect, it } from 'vitest'

import {
  isMindClassroomQueueBusy,
  mindClassroomProgressBranchName,
  mindClassroomProgressStats,
  mindClassroomStartFillPercent,
  mindClassroomStartLabelKey,
  shouldShowMindClassroomRestart,
} from '@/utils/mindClassroomLaunchState'

describe('mindClassroomLaunchState', () => {
  it('locks the start button while the job is in flight', () => {
    expect(isMindClassroomQueueBusy('queued')).toBe(true)
    expect(isMindClassroomQueueBusy('planning')).toBe(true)
    expect(isMindClassroomQueueBusy('generating')).toBe(true)
    expect(isMindClassroomQueueBusy(null, true)).toBe(true)
    expect(isMindClassroomQueueBusy('ready')).toBe(false)
    expect(isMindClassroomQueueBusy(null)).toBe(false)
    expect(isMindClassroomQueueBusy('ready', false, 'loading')).toBe(true)
    expect(isMindClassroomQueueBusy('ready', false, 'ready')).toBe(false)
  })

  it('maps prep stages onto the start-button label', () => {
    expect(mindClassroomStartLabelKey({ jobStatus: 'planning' })).toBe(
      'canvas.mindClassroom.queue.planning'
    )
    expect(
      mindClassroomStartLabelKey({ jobStatus: 'generating', presentation: 'canvas_tour' })
    ).toBe('canvas.mindClassroom.queue.transcript')
    expect(
      mindClassroomStartLabelKey({
        jobStatus: 'generating',
        presentation: 'canvas_tour',
        branchName: '呼吸作用',
      })
    ).toBe('canvas.mindClassroom.queue.transcriptBranch')
    expect(mindClassroomProgressBranchName({ branch_label: '呼吸作用' })).toBe('呼吸作用')
    expect(mindClassroomProgressBranchName({ branch_labels: ['光合作用', '呼吸作用'] })).toBe(
      '光合作用'
    )
    expect(
      mindClassroomProgressBranchName({
        branch_label: '过期名',
        branches: [
          { index: 1, label: '第一支', state: 'done' },
          { index: 2, label: '呼吸作用', state: 'streaming' },
        ],
      })
    ).toBe('呼吸作用')
    expect(
      mindClassroomStartLabelKey({
        jobStatus: 'generating',
        presentation: 'canvas_tour',
        ttsReady: true,
        hasPrepared: true,
        voiceWarmup: 'loading',
        branchName: '呼吸作用',
      })
    ).toBe('canvas.mindClassroom.queue.transcriptBranch')
    expect(
      mindClassroomStartLabelKey({
        jobStatus: 'generating',
        presentation: 'canvas_tour',
        ttsReady: true,
        hasPrepared: true,
        voiceWarmup: 'loading',
        remaining: 4,
        branchName: '呼吸作用',
      })
    ).toBe('canvas.mindClassroom.queue.transcriptRemaining')
    expect(
      mindClassroomStartLabelKey({
        jobStatus: 'generating',
        presentation: 'canvas_tour',
        ttsReady: true,
        hasPrepared: true,
        voiceWarmup: 'ready',
        remaining: 4,
        branchName: '呼吸作用',
      })
    ).toBe('canvas.mindClassroom.queue.transcriptRemaining')
    expect(
      mindClassroomStartLabelKey({
        jobStatus: 'generating',
        presentation: 'canvas_tour',
        ttsReady: true,
        hasPrepared: true,
        voiceWarmup: 'loading',
        remaining: 0,
      })
    ).toBe('canvas.mindClassroom.queue.loadingVoice')
    expect(
      mindClassroomStartLabelKey({ jobStatus: 'generating', presentation: 'slide_deck' })
    ).toBe('canvas.mindClassroom.queue.generating')
    expect(
      mindClassroomStartLabelKey({
        jobStatus: 'ready',
        hasPrepared: true,
        voiceWarmup: 'loading',
      })
    ).toBe('canvas.mindClassroom.queue.loadingVoice')
    expect(mindClassroomStartLabelKey({ jobStatus: 'ready', hasPrepared: true })).toBe(
      'canvas.mindClassroom.queue.ready'
    )
    expect(mindClassroomStartLabelKey({ jobStatus: 'failed' })).toBe(
      'canvas.mindClassroom.queue.failed'
    )
    expect(mindClassroomStartLabelKey({ jobStatus: null })).toBe('canvas.mindClassroom.start')
    expect(
      mindClassroomProgressStats({
        tts_ready: true,
        branches: [
          { index: 1, label: '开场', state: 'done' },
          { index: 2, label: '第二支', state: 'streaming' },
        ],
      })
    ).toEqual({
      branchName: '第二支',
      ttsReady: true,
      done: 1,
      total: 2,
      inFlight: 1,
    })
  })

  it('fills the start button from finished branch count', () => {
    expect(mindClassroomStartFillPercent(0, 0)).toBe(0)
    expect(mindClassroomStartFillPercent(0, 6)).toBe(0)
    expect(mindClassroomStartFillPercent(1, 6)).toBe(17)
    expect(mindClassroomStartFillPercent(3, 6)).toBe(50)
    expect(mindClassroomStartFillPercent(6, 6)).toBe(100)
    expect(mindClassroomStartFillPercent(9, 6)).toBe(100)
  })

  it('shows restart once a job exists or a script is ready', () => {
    expect(shouldShowMindClassroomRestart({ jobStatus: null })).toBe(false)
    expect(shouldShowMindClassroomRestart({ jobStatus: 'planning' })).toBe(true)
    expect(shouldShowMindClassroomRestart({ jobStatus: 'ready', hasPrepared: true })).toBe(true)
    expect(shouldShowMindClassroomRestart({ jobStatus: 'failed' })).toBe(true)
    expect(
      shouldShowMindClassroomRestart({ jobStatus: 'ready', hasPrepared: true, authenticated: false })
    ).toBe(false)
  })
})
