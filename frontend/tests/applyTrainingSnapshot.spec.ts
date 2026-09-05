import { describe, expect, it, vi } from 'vitest'

import {
  applyTrainingNavigate,
  canSeeTrainingSpeakerNotes,
  chipTopicOverride,
  isTrainingRoomArmed,
  liveLessonCoversMedia,
  liveLessonStep,
  shouldAcceptTrainingSnapshot,
  shouldBypassTrainingLeaveConfirm,
  shouldForceNavigate,
  teachersSeeTrainingBanner,
  trainingCanvasLocation,
  trainingFollowCursorResets,
  trainingSteerMode,
} from '@/composables/training/applyTrainingSnapshot'
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
    ...overrides,
  }
}

describe('armed room', () => {
  it('is ready after Start and hides the teacher banner until a course plays', () => {
    const armed = snapshot({ course_id: null, diagram_type: null, pull_users: false })
    expect(isTrainingRoomArmed(armed)).toBe(true)
    expect(teachersSeeTrainingBanner(armed)).toBe(false)
    expect(isTrainingRoomArmed(snapshot({ course_id: 'c1' }))).toBe(false)
    expect(teachersSeeTrainingBanner(snapshot({ course_id: 'c1' }))).toBe(true)
    expect(shouldForceNavigate(armed, 0)).toBe(false)
    expect(trainingSteerMode(armed)).toBe('free')
    expect(trainingSteerMode(snapshot({ course_id: 'c1', pull_users: true }))).toBe('pull')
  })
})

describe('liveLessonStep', () => {
  it('paints page marks for teachers during live and paused play', () => {
    const page = snapshot({
      step: {
        position: 0,
        type: 'page',
        page_key: 'canvas',
        overlays: [{ kind: 'text', text: '看这里', x: 50, y: 40 }],
      },
    })
    expect(liveLessonStep(page, {})?.overlays?.[0]?.kind).toBe('text')
    expect(liveLessonCoversMedia(page.step)).toBe(false)
    expect(liveLessonStep(snapshot({ state: 'paused', step: page.step }), {})).not.toBeNull()
    expect(liveLessonStep(page, { skip: true })).toBeNull()
    expect(liveLessonStep(page, { trainingRoute: true })).toBeNull()
    expect(liveLessonStep(snapshot({ state: 'ended', step: page.step }), {})).toBeNull()
    expect(liveLessonStep(snapshot({ pull_users: false, step: page.step }), {})).toBeNull()
  })

  it('covers the viewport only when a slide or video has a file', () => {
    expect(
      liveLessonCoversMedia({
        position: 0,
        type: 'slide',
        asset_url: '/api/training/assets/x',
      })
    ).toBe(true)
    expect(liveLessonCoversMedia({ position: 0, type: 'slide' })).toBe(false)
    expect(liveLessonCoversMedia({ position: 0, type: 'page', page_key: 'mindgraph' })).toBe(false)
  })
})

describe('canSeeTrainingSpeakerNotes', () => {
  it('shows notes only to the session instructor', () => {
    expect(canSeeTrainingSpeakerNotes(snapshot(), 1)).toBe(true)
    expect(canSeeTrainingSpeakerNotes(snapshot(), 2)).toBe(false)
    expect(canSeeTrainingSpeakerNotes(snapshot({ state: 'none' }), 1)).toBe(false)
  })
})

describe('shouldAcceptTrainingSnapshot', () => {
  it('accepts a new live session even when the previous seq was higher', () => {
    const ended = snapshot({
      state: 'ended',
      session_id: 'sess-old',
      seq: 21,
    })
    const next = snapshot({
      state: 'live',
      session_id: 'sess-new',
      seq: 1,
      diagram_type: 'double_bubble_map',
    })
    expect(shouldAcceptTrainingSnapshot(ended, next)).toBe(true)
    expect(trainingFollowCursorResets(ended, next)).toBe(true)
  })

  it('still drops an older seq on the same session', () => {
    expect(shouldAcceptTrainingSnapshot(snapshot({ seq: 6 }), snapshot({ seq: 5 }))).toBe(
      false
    )
  })

  it('does not replace a live session with a different ended tombstone', () => {
    expect(
      shouldAcceptTrainingSnapshot(
        snapshot({ session_id: 'sess-live', seq: 2 }),
        snapshot({ state: 'ended', session_id: 'sess-old', seq: 21 })
      )
    ).toBe(false)
  })
})

describe('shouldForceNavigate', () => {
  it('applies a higher live seq with a diagram type', () => {
    expect(shouldForceNavigate(snapshot({ seq: 5 }), 4)).toBe(true)
  })

  it('ignores a stale or equal seq', () => {
    expect(shouldForceNavigate(snapshot({ seq: 4 }), 4)).toBe(false)
    expect(shouldForceNavigate(snapshot({ seq: 3 }), 4)).toBe(false)
  })

  it('does not force-nav while paused', () => {
    expect(shouldForceNavigate(snapshot({ state: 'paused', seq: 9 }), 4)).toBe(false)
  })

  it('does not force-nav after the session ends', () => {
    expect(shouldForceNavigate(snapshot({ state: 'ended', seq: 9 }), 4)).toBe(false)
    expect(shouldBypassTrainingLeaveConfirm('ended')).toBe(true)
    expect(shouldBypassTrainingLeaveConfirm('none')).toBe(false)
  })

  it('does not force-nav while the instructor released the room', () => {
    expect(shouldForceNavigate(snapshot({ seq: 9, pull_users: false }), 4)).toBe(false)
  })

  it('pulls again after free when the session flag is back on', () => {
    expect(
      shouldForceNavigate(
        snapshot({
          seq: 10,
          pull_users: true,
          step: { position: 0, type: 'page', page_key: 'canvas', pull_users: false },
        }),
        9
      )
    ).toBe(true)
  })

  it('does not force-nav without a diagram type', () => {
    expect(shouldForceNavigate(snapshot({ diagram_type: null, seq: 9 }), 4)).toBe(false)
  })

  it('does not force-nav a slide step', () => {
    expect(
      shouldForceNavigate(
        snapshot({
          seq: 9,
          step: { position: 1, type: 'slide', asset_url: '/api/training/assets/x' },
        }),
        4
      )
    ).toBe(false)
  })
})

describe('trainingCanvasLocation', () => {
  it('maps allowlisted types onto desktop or mobile canvas', () => {
    expect(trainingCanvasLocation('/mindmate', 'double_bubble_map')).toEqual({
      path: '/canvas',
      query: { type: 'double_bubble_map' },
    })
    expect(trainingCanvasLocation('/m/mindmate', 'circle_map')).toEqual({
      path: '/m/canvas',
      query: { type: 'circle_map' },
    })
  })

  it('rejects unknown types', () => {
    expect(trainingCanvasLocation('/canvas', '/mindmate')).toBeNull()
    expect(trainingCanvasLocation('/canvas', 'not_a_diagram')).toBeNull()
  })
})

describe('applyTrainingNavigate', () => {
  it('pushes the instructor jump target once', async () => {
    const push = vi.fn().mockResolvedValue(undefined)
    const router = {
      push,
      currentRoute: { value: { path: '/mindmate', query: {} } },
    }
    const ok = await applyTrainingNavigate(
      router as never,
      '/mindmate',
      snapshot({ diagram_type: 'tree_map' })
    )
    expect(ok).toBe(true)
    expect(push).toHaveBeenCalledWith({ path: '/canvas', query: { type: 'tree_map' } })
  })

  it('skips push when already on that canvas type', async () => {
    const push = vi.fn()
    const router = {
      push,
      currentRoute: { value: { path: '/canvas', query: { type: 'tree_map' } } },
    }
    const ok = await applyTrainingNavigate(
      router as never,
      '/canvas',
      snapshot({ diagram_type: 'tree_map' })
    )
    expect(ok).toBe(true)
    expect(push).not.toHaveBeenCalled()
  })
})

describe('chipTopicOverride', () => {
  it('joins double-bubble items', () => {
    expect(chipTopicOverride({ id: '1', label: 'ice', item_a: 'ice', item_b: 'water' })).toBe(
      'ice vs water'
    )
  })
})
