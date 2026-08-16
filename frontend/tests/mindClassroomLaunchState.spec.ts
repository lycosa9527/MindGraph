import { describe, expect, it } from 'vitest'

import {
  isMindClassroomQueueBusy,
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
  })

  it('maps prep stages onto the start-button label', () => {
    expect(mindClassroomStartLabelKey({ jobStatus: 'planning' })).toBe(
      'canvas.mindClassroom.queue.planning'
    )
    expect(
      mindClassroomStartLabelKey({ jobStatus: 'generating', presentation: 'canvas_tour' })
    ).toBe('canvas.mindClassroom.queue.transcript')
    expect(
      mindClassroomStartLabelKey({ jobStatus: 'generating', presentation: 'slide_deck' })
    ).toBe('canvas.mindClassroom.queue.generating')
    expect(mindClassroomStartLabelKey({ jobStatus: 'ready', hasPrepared: true })).toBe(
      'canvas.mindClassroom.queue.ready'
    )
    expect(mindClassroomStartLabelKey({ jobStatus: 'failed' })).toBe(
      'canvas.mindClassroom.queue.failed'
    )
    expect(mindClassroomStartLabelKey({ jobStatus: null })).toBe('canvas.mindClassroom.start')
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
