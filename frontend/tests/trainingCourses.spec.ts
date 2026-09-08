import { describe, expect, it } from 'vitest'

import {
  isMediaTrainingStep,
  shouldForceNavigate,
  trainingCanvasLocation,
  trainingStepLocation,
} from '@/composables/training/applyTrainingSnapshot'
import {
  addOverlay,
  applyDiagramCardStep,
  applyModalKey,
  applyPageKey,
  blankPageStep,
  blankSlideStep,
  insertStepsAt,
  selectedIndexAfterRemove,
  stepSpotlight,
  mergeSavedStepMeta,
  trainingCourseFingerprint,
  trainingCourseWriteBody,
  uploadedSlideSteps,
} from '@/composables/training/trainingBuilderSteps'
import {
  addMarkStep,
  advancePlayCursor,
  canAdvancePlayCursor,
  canSteerLiveSnapshot,
  currentMarkStep,
  removeMarkStep,
  visibleMarkOverlays,
} from '@/composables/training/trainingMarkSteps'
import { applyTrainingTopicToDiagram } from '@/composables/training/trainingTopicApply'
import {
  isTrainingTopicsDrag,
  isTrainingTopicsDrop,
  normalizeTopicOptions,
  stepUsesDualTopics,
  TRAINING_TOPICS_DRAG,
} from '@/composables/training/trainingTopicOptions'
import { hasTrainingLivePreview } from '@/config/trainingPageLive'
import { TRAINING_PAGES, trainingPagePath } from '@/config/trainingPages'
import {
  shouldBlockTrainingAuthoringClick,
  trainingFocusDef,
  trainingFocusOptions,
  trainingModalsForPage,
} from '@/config/trainingUiTargets'
import type { TrainingSnapshot } from '@/types/training'

function snapshot(overrides: Partial<TrainingSnapshot> = {}): TrainingSnapshot {
  return {
    state: 'live',
    session_id: 'sess-1',
    org_id: 10,
    seq: 5,
    diagram_type: 'double_bubble_map',
    topic_options: [],
    instructor_id: 1,
    instructor_name: 'Ada',
    course_id: '6f2a1c90-db01-4000-8000-00000000db01',
    step_index: 0,
    step: {
      position: 0,
      type: 'canvas',
      diagram_type: 'double_bubble_map',
    },
    ...overrides,
  }
}

describe('training course playback', () => {
  it('does not force-nav on slide or video steps', () => {
    const slide = snapshot({
      step: {
        position: 1,
        type: 'slide',
        asset_url: '/api/training/assets/courses/x/slides/a.png',
        pull_users: true,
      },
      diagram_type: null,
    })
    expect(isMediaTrainingStep(slide)).toBe(true)
    expect(shouldForceNavigate(slide, 4)).toBe(false)
  })

  it('still force-navs a live canvas step', () => {
    expect(shouldForceNavigate(snapshot(), 4)).toBe(true)
  })

  it('pulls teachers to a selected app page when the box is checked', () => {
    const landing = snapshot({
      diagram_type: null,
      step: {
        position: 0,
        type: 'page',
        page_key: 'mindgraph',
        pull_users: true,
      },
    })
    expect(shouldForceNavigate(landing, 4)).toBe(true)
    expect(trainingStepLocation('/library', landing)).toEqual({ path: '/mindgraph' })
    expect(trainingStepLocation('/mindgraph', landing)).toEqual({ path: '/mindgraph' })
    expect(trainingStepLocation('/mindmate', landing)).toEqual({ path: '/mindgraph' })
    expect(trainingPagePath('/m/home', 'mindgraph')).toBe('/m/mindgraph')
    expect(trainingPagePath('/mindgraph', 'mindgraph')).toBe('/mindgraph')
    expect(trainingPagePath('/mindmate', 'mindgraph')).toBe('/mindgraph')
    expect(trainingPagePath('/maite', 'maite')).toBe('/maite')
    expect(trainingCanvasLocation('/mindgraph', 'double_bubble_map')).toEqual({
      path: '/canvas',
      query: { type: 'double_bubble_map' },
    })
    expect(hasTrainingLivePreview('mindgraph')).toBe(true)
    expect(hasTrainingLivePreview('canvas')).toBe(true)
    expect(hasTrainingLivePreview('auth')).toBe(true)
    expect(hasTrainingLivePreview('mindmate')).toBe(true)
    expect(hasTrainingLivePreview('library')).toBe(true)
    expect(TRAINING_PAGES.map((page) => page.key)).toEqual(
      expect.arrayContaining([
        'auth',
        'mindgraph',
        'canvas',
        'mindmate',
        'askonce',
        'library',
        'thinking-coins',
      ])
    )
    const register = snapshot({
      diagram_type: null,
      step: { position: 0, type: 'page', page_key: 'auth', pull_users: true },
    })
    expect(trainingStepLocation('/mindgraph', register)).toEqual({
      path: '/auth',
      query: { training: '1' },
    })
    expect(trainingCanvasLocation('/library', 'mind_map')).toEqual({
      path: '/canvas',
      query: { type: 'mindmap' },
    })
  })

  it('keeps a closed catalog of landing cards and language-settings buttons', () => {
    const cards = trainingFocusOptions('mindgraph', null)
    expect(cards.some((item) => item.key === 'diagram-double_bubble_map')).toBe(true)
    expect(trainingFocusOptions('mindgraph', 'language-settings').map((item) => item.key)).toEqual([
      'mindmap-v1',
      'mindmap-v2',
    ])
    expect(trainingFocusOptions('auth', null).map((item) => item.key)).toEqual([
      'auth-login',
      'auth-register',
    ])
    expect(trainingFocusOptions('canvas', null).map((item) => item.key)).toEqual([
      'canvas-add',
      'canvas-delete',
    ])
    expect(shouldBlockTrainingAuthoringClick('diagram-double_bubble_map')).toBe(true)
    expect(shouldBlockTrainingAuthoringClick('auth-register')).toBe(false)
    expect(trainingFocusDef('auth-register')?.activateOnApply).toBe(true)
    expect(trainingFocusDef('canvas-add')?.activateOnApply).toBeFalsy()
  })

  it('drops a page button when the slide leaves that page', () => {
    const step = blankPageStep(0)
    step.focus_key = 'diagram-mindmap'
    applyPageKey(step, 'mindmate')
    expect(step.focus_key).toBeNull()
    applyModalKey(step, 'language-settings')
    applyPageKey(step, 'mindgraph')
    step.focus_key = 'mindmap-v2'
    applyModalKey(step, null)
    expect(step.focus_key).toBeNull()
  })

  it('opens the mind map canvas when a landing card is applied', () => {
    const step = blankPageStep(0)
    expect(applyDiagramCardStep(step, 'diagram-mindmap')).toBe(true)
    expect(step.page_key).toBe('canvas')
    expect(step.type).toBe('canvas')
    expect(step.diagram_type).toBe('mindmap')
    expect(applyDiagramCardStep(step, 'auth-register')).toBe(false)
  })

  it('uses two topic fields on double bubble and one field on other diagrams', () => {
    const bubble = blankPageStep(0)
    applyPageKey(bubble, 'canvas')
    expect(bubble.diagram_type).toBe('double_bubble_map')
    expect(stepUsesDualTopics(bubble)).toBe(true)
    bubble.diagram_type = 'mindmap'
    expect(stepUsesDualTopics(bubble)).toBe(false)
    expect(
      normalizeTopicOptions(
        [
          { id: '1', label: '', item_a: 'ice', item_b: 'water' },
          { id: '2', label: '', item_a: 'only-left', item_b: '' },
        ],
        true
      )
    ).toEqual([{ id: '1', label: 'ice vs water', item_a: 'ice', item_b: 'water', prompt: null }])
    expect(
      normalizeTopicOptions([{ id: '3', label: '', prompt: '密度' }], false)
    ).toEqual([{ id: '3', label: '密度', item_a: null, item_b: null, prompt: '密度' }])
  })

  it('places a topics overlay on the current mark step', () => {
    const step = blankPageStep(0)
    step.mark_step = 4
    step.mark_steps = 4
    step.overlays = [
      { kind: 'text', x: 10, y: 10, text: 'a', step: 2 },
      { kind: 'text', x: 12, y: 12, text: 'b', step: 3 },
      { kind: 'text', x: 14, y: 14, text: 'c', step: 4 },
    ]
    addOverlay(step, 'topics', { x: 10, y: 12, step: 4 })
    addOverlay(step, 'topics', { x: 41, y: 58, step: 4 })
    expect(step.overlays.filter((row) => row.kind === 'topics')).toHaveLength(1)
    expect(step.overlays.at(-1)).toMatchObject({ kind: 'topics', x: 41, y: 58, step: 4 })
    expect(currentMarkStep(step)).toBe(4)
    expect(visibleMarkOverlays(step).filter((row) => row.kind === 'topics')).toHaveLength(1)
  })

  it('fills double-bubble topic nodes from a selected option', () => {
    const written: Record<string, string> = {}
    applyTrainingTopicToDiagram(
      {
        updateNode: (id, updates) => {
          written[id] = updates.text
          return true
        },
      },
      { id: '1', label: 'ice vs water', item_a: 'ice', item_b: 'water' }
    )
    expect(written).toEqual({ 'left-topic': 'ice', 'right-topic': 'water' })
  })

  it('recognizes a topics drag payload', () => {
    const transfer = {
      types: [TRAINING_TOPICS_DRAG, 'text/plain'],
      getData: (type: string) => (type === TRAINING_TOPICS_DRAG ? '1' : 'topics'),
    } as DataTransfer
    expect(isTrainingTopicsDrag(transfer)).toBe(true)
    expect(isTrainingTopicsDrop(transfer)).toBe(true)
    expect(isTrainingTopicsDrop({ types: ['text/plain'], getData: () => 'nope' } as DataTransfer)).toBe(
      false
    )
  })

  it('starts a slide with empty speaker notes', () => {
    expect(blankPageStep(0).notes).toBe('')
  })

  it('adds a PPT image as a media slide that teachers follow', () => {
    const step = blankSlideStep(2)
    expect(step).toMatchObject({
      position: 2,
      type: 'slide',
      page_key: null,
      pull_users: true,
    })
  })

  it('inserts image slides at the current index and shifts the rest down', () => {
    const steps = [blankPageStep(0), blankPageStep(1), blankPageStep(2)]
    steps[2].focus_key = 'old-three'
    const created = uploadedSlideSteps(2, [
      { id: 'a1', url: '/api/training/assets/courses/x/slides/a.png' },
    ])
    const at = insertStepsAt(steps, 2, created)
    expect(at).toBe(2)
    expect(steps.map((step) => step.type)).toEqual(['page', 'page', 'slide', 'page'])
    expect(steps.map((step) => step.position)).toEqual([0, 1, 2, 3])
    expect(steps[2]?.asset_id).toBe('a1')
    expect(steps[2]?.asset_url).toContain('slides/a.png')
    expect(steps[3]?.focus_key).toBe('old-three')
  })

  it('saves title as a plain string, not a Vue ref', () => {
    const step = blankPageStep(0)
    step.page_key = 'auth'
    step.focus_key = 'auth-register'
    step.thumb_id = 'thumb-1'
    step.thumb_url = 'data:image/png;base64,aaaa'
    step.asset_url = 'data:image/png;base64,bbbb'
    const body = trainingCourseWriteBody('登录课', '备注', [step])
    const encoded = JSON.stringify(body)
    expect(encoded).not.toContain('__v_isRef')
    expect(encoded).not.toContain('data:image/png')
    expect(body.title).toBe('登录课')
    expect(body.steps[0]?.focus_key).toBe('auth-register')
    expect(body.steps[0]?.thumb_id).toBe('thumb-1')
    expect(body.steps[0]?.thumb_url).toBeUndefined()
  })

  it('fingerprints the course without volatile step ids', () => {
    const step = blankPageStep(0)
    step.overlays = [{ kind: 'text', x: 20, y: 18, text: '注册' }]
    const before = trainingCourseFingerprint('登录课', '', [step])
    step.id = 'server-1'
    expect(trainingCourseFingerprint('登录课', '', [step])).toBe(before)
    step.overlays[0].text = '邀请码'
    expect(trainingCourseFingerprint('登录课', '', [step])).not.toBe(before)
  })

  it('merges saved step ids onto the live draft', () => {
    const local = [blankPageStep(0)]
    local[0].notes = '讲稿'
    mergeSavedStepMeta(local, [
      {
        ...blankPageStep(0),
        id: 'step-1',
        thumb_id: 'thumb-1',
        thumb_url: '/api/training/assets/thumbs/a.png',
      },
    ])
    expect(local[0].id).toBe('step-1')
    expect(local[0].thumb_id).toBe('thumb-1')
    expect(local[0].notes).toBe('讲稿')
  })

  it('only offers account and language-settings on the landing page', () => {
    expect(trainingModalsForPage('mindgraph').map((modal) => modal.key)).toEqual([
      'account',
      'language-settings',
      'thinking-coins',
      'update-log',
    ])
    expect(trainingModalsForPage('canvas').map((modal) => modal.key)).toEqual([
      'online-collab',
      'export-community',
    ])
    expect(trainingModalsForPage('library').map((modal) => modal.key)).toEqual(['login'])
    expect(trainingModalsForPage('auth')).toEqual([])
    const step = blankPageStep(0)
    applyModalKey(step, 'account')
    applyPageKey(step, 'canvas')
    expect(step.modal_key).toBeNull()
  })

  it('does not pull when the instructor released the room', () => {
    const stay = snapshot({
      pull_users: false,
      diagram_type: null,
      step: {
        position: 0,
        type: 'page',
        page_key: 'mindgraph',
      },
    })
    expect(shouldForceNavigate(stay, 4)).toBe(false)
  })

  it('places a role overlay that can sit on the page', () => {
    const step = blankPageStep(0)
    addOverlay(step, 'role', { role: '11-clap' })
    expect(step.mark_step).toBe(1)
    expect(visibleMarkOverlays(step)).toMatchObject([
      { kind: 'role', role: '11-clap', x: 82, y: 74, w: 18, step: 1 },
    ])
    addOverlay(step, 'role', { role: 'not-a-role' })
    expect(visibleMarkOverlays(step)[1]).toMatchObject({ kind: 'role', role: '01-look-here' })
  })

  it('places a spotlight overlay and keeps selection after deleting a slide', () => {
    const step = blankPageStep(0)
    addOverlay(step, 'spotlight')
    expect(step.mark_step).toBe(1)
    expect(stepSpotlight(step)).toMatchObject({
      kind: 'spotlight',
      x: 50,
      y: 50,
      r: 1,
      shape: 'circle',
      step: 1,
    })
    expect(selectedIndexAfterRemove(2, 0, 3)).toBe(1)
    expect(selectedIndexAfterRemove(0, 0, 2)).toBe(0)
    expect(selectedIndexAfterRemove(1, 1, 1)).toBe(0)
  })

  it('keeps spotlight role and text on the current step until a step is added by hand', () => {
    const step = blankPageStep(0)
    expect(visibleMarkOverlays(step)).toEqual([])
    addOverlay(step, 'spotlight')
    addOverlay(step, 'role', { role: '11-clap' })
    addOverlay(step, 'text', { text: 'hint' })
    expect(currentMarkStep(step)).toBe(1)
    expect(step.mark_steps).toBe(1)
    expect(visibleMarkOverlays(step).map((row) => row.kind)).toEqual([
      'spotlight',
      'role',
      'text',
    ])
    addMarkStep(step)
    addOverlay(step, 'arrow')
    expect(currentMarkStep(step)).toBe(2)
    expect(visibleMarkOverlays({ ...step, mark_step: 1 }).map((row) => row.kind)).toEqual([
      'spotlight',
      'role',
      'text',
    ])
    expect(visibleMarkOverlays(step).map((row) => row.kind)).toEqual([
      'spotlight',
      'role',
      'text',
      'arrow',
    ])
    removeMarkStep(step)
    expect(step.mark_step).toBe(1)
    expect(visibleMarkOverlays(step).map((row) => row.kind)).toEqual([
      'spotlight',
      'role',
      'text',
    ])
  })

  it('advances preview like a deck: mark clicks first, then the next slide', () => {
    const first = blankPageStep(0)
    addOverlay(first, 'text', { text: 'a' })
    addMarkStep(first)
    addOverlay(first, 'text', { text: 'b' })
    first.mark_step = 1
    const second = blankPageStep(1)
    const deck = [first, second]
    expect(canAdvancePlayCursor(deck, 0, 1)).toBe(true)
    expect(advancePlayCursor(deck, 0, 1)).toBe(0)
    expect(currentMarkStep(first)).toBe(2)
    expect(advancePlayCursor(deck, 0, 1)).toBe(1)
    expect(currentMarkStep(second)).toBe(1)
    expect(advancePlayCursor(deck, 1, -1)).toBe(0)
    expect(currentMarkStep(first)).toBe(2)
  })

  it('enables live pad prev/next from snapshot cursor, not the full deck', () => {
    const first = blankPageStep(0)
    addMarkStep(first)
    first.mark_step = 1
    const live = {
      state: 'live' as const,
      session_id: 's',
      org_id: 1,
      seq: 2,
      diagram_type: null,
      topic_options: [],
      instructor_id: 1,
      instructor_name: 'Ada',
      step: first,
      step_index: 0,
      step_count: 2,
    }
    expect(canSteerLiveSnapshot(live, -1)).toBe(false)
    expect(canSteerLiveSnapshot(live, 1)).toBe(true)
    first.mark_step = 2
    live.step_index = 1
    expect(canSteerLiveSnapshot(live, -1)).toBe(true)
    expect(canSteerLiveSnapshot(live, 1)).toBe(false)
  })
})
