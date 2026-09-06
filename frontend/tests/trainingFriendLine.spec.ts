import { describe, expect, it } from 'vitest'

import {
  trainingActivityPageKey,
  trainingFriendJumpSnapshot,
  trainingFriendLine,
} from '@/composables/training/trainingFriendLine'
import { trainingPageKeyFromPath } from '@/config/trainingPages'
import type { TrainingSnapshot } from '@/types/training'

function snapshot(overrides: Partial<TrainingSnapshot> = {}): TrainingSnapshot {
  return {
    state: 'live',
    session_id: 'sess-1',
    org_id: 10,
    seq: 3,
    diagram_type: 'double_bubble_map',
    topic_options: [],
    instructor_id: 1,
    instructor_name: 'Ada',
    pull_users: true,
    step: {
      position: 0,
      type: 'page',
      page_key: 'mindmate',
    },
    ...overrides,
  }
}

describe('training friend line', () => {
  it('reads the live page from the route when the room is free', () => {
    expect(trainingPageKeyFromPath('/m/canvas')).toBe('canvas')
    expect(trainingPageKeyFromPath('/mindgraph')).toBe('mindgraph')
    expect(trainingActivityPageKey('/library', snapshot({ pull_users: false }))).toBe('library')
    expect(trainingActivityPageKey('/library', snapshot())).toBe('mindmate')
    expect(
      trainingActivityPageKey('/mindgraph', snapshot({
        step: { position: 0, type: 'slide', asset_url: '/s.png' },
      }))
    ).toBe('slide')
  })

  it('formats name / page / topic like the classic friends list', () => {
    const line = trainingFriendLine(
      {
        user_id: 9,
        name: '王寸尺',
        page_key: 'canvas',
        option_label: 'ice vs water',
      },
      (key) => {
        if (key === 'training.builder.pageCanvas') return 'Canvas'
        return key
      }
    )
    expect(line).toBe('王寸尺 / Canvas / ice vs water')
    expect(
      trainingFriendLine({ user_id: 4, page_key: 'slide' }, (key) =>
        key === 'training.pageSlide' ? 'Slide' : key
      )
    ).toBe('4 / Slide / —')
  })

  it('jumps to a friend’s page even without a diagram type', () => {
    const live = snapshot({ diagram_type: null })
    const target = trainingFriendJumpSnapshot(live, {
      user_id: 8,
      page_key: 'library',
    })
    expect(target?.step?.page_key).toBe('library')
    expect(trainingFriendJumpSnapshot(live, { user_id: 8, page_key: 'slide' })).toBeNull()
    expect(trainingFriendJumpSnapshot(live, { user_id: 8 })).toBeNull()
  })
})
