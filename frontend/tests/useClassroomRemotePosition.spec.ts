import { describe, expect, it } from 'vitest'

import {
  CLASSROOM_REMOTE_TABS,
  DEFAULT_CLASSROOM_REMOTE_TAB,
} from '@/canvas-ribbon/mindMapClassroomRemoteTypes'
import {
  clampClassroomRemotePosition,
  defaultClassroomRemotePosition,
  parseClassroomRemotePersisted,
} from '@/composables/canvas/useClassroomRemotePosition'

describe('classroom remote position', () => {
  it('clamps inside the viewport with a margin', () => {
    expect(clampClassroomRemotePosition(-40, -20, 240, 400, 1280, 720, 8)).toEqual({
      left: 8,
      top: 8,
    })
    expect(clampClassroomRemotePosition(2000, 2000, 240, 400, 1280, 720, 8)).toEqual({
      left: 1032,
      top: 312,
    })
  })

  it('defaults to the bottom-right above the status bar', () => {
    const pos = defaultClassroomRemotePosition(240, 400, 1280, 720)
    expect(pos.left).toBe(1024)
    expect(pos.top).toBe(264)
  })

  it('parses a stored remote and rejects junk', () => {
    expect(parseClassroomRemotePersisted(null)).toBeNull()
    expect(parseClassroomRemotePersisted('{')).toBeNull()
    expect(
      parseClassroomRemotePersisted(
        JSON.stringify({ left: 80, top: 120, collapsed: true, tab: 'teaching' })
      )
    ).toEqual({
      left: 80,
      top: 120,
      hidden: false,
      tab: 'teaching',
    })
    expect(
      parseClassroomRemotePersisted(JSON.stringify({ left: 80, top: 120, tab: 'nope' }))
    ).toEqual({
      left: 80,
      top: 120,
      hidden: false,
      tab: DEFAULT_CLASSROOM_REMOTE_TAB,
    })
    expect(
      parseClassroomRemotePersisted(
        JSON.stringify({ left: 80, top: 120, hidden: true, tab: 'view' })
      )
    ).toEqual({
      left: 80,
      top: 120,
      hidden: true,
      tab: 'view',
    })
    expect([...CLASSROOM_REMOTE_TABS]).toEqual(['view', 'edit', 'teaching', 'topics', 'ai', 'file'])
  })
})
