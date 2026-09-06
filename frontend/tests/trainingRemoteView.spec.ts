import { describe, expect, it } from 'vitest'

import {
  trainingRemotePhase,
  trainingRemotePrompterKey,
  trainingRemoteShouldPollHost,
} from '@/composables/training/trainingRemoteView'
import type { TrainingSnapshot } from '@/types/training'

function snapshot(overrides: Partial<TrainingSnapshot> = {}): TrainingSnapshot {
  return {
    state: 'live',
    session_id: 'sess-1',
    org_id: 10,
    seq: 4,
    diagram_type: 'double_bubble_map',
    topic_options: [],
    instructor_id: 1,
    instructor_name: 'Ada',
    course_id: 'c1',
    ...overrides,
  }
}

describe('trainingRemoteView', () => {
  it('waits until this instructor has a playing course', () => {
    expect(trainingRemotePhase(snapshot({ course_id: null }), 1)).toBe('waiting')
    expect(trainingRemotePhase(snapshot({ state: 'ended' }), 1)).toBe('waiting')
    expect(trainingRemotePhase(snapshot({ state: 'none', course_id: null }), 1)).toBe(
      'waiting'
    )
  })

  it('shows a foreign host instead of steer controls', () => {
    expect(trainingRemotePhase(snapshot(), 9)).toBe('foreign')
  })

  it('opens the live remote for the host, including pause', () => {
    expect(trainingRemotePhase(snapshot(), 1)).toBe('live')
    expect(trainingRemotePhase(snapshot({ state: 'paused' }), 1)).toBe('live')
  })

  it('changes the prompter key when the step seq moves', () => {
    expect(trainingRemotePrompterKey(snapshot({ seq: 4 }))).not.toBe(
      trainingRemotePrompterKey(snapshot({ seq: 5 }))
    )
  })

  it('polls the hosted pointer only while waiting or the school is unknown', () => {
    expect(trainingRemoteShouldPollHost('waiting', null)).toBe(true)
    expect(trainingRemoteShouldPollHost('waiting', 10)).toBe(true)
    expect(trainingRemoteShouldPollHost('live', 10)).toBe(false)
    expect(trainingRemoteShouldPollHost('foreign', 10)).toBe(false)
    expect(trainingRemoteShouldPollHost('live', null)).toBe(true)
  })
})
