import { describe, expect, it } from 'vitest'

import {
  SEMINAR_CHAT_MIN_READING_PX,
  SEMINAR_TASK_DRAWER_PX,
  SEMINAR_TASK_RAIL_PX,
  seminarDocPaneBudget,
} from '@/composables/mindmate/mindmateSeminarChrome'

describe('seminarDocPaneBudget', () => {
  it('leaves room for the right rail while reading', () => {
    const width = seminarDocPaneBudget(1200, { drawerOpen: false, reading: true })
    expect(width).toBe(1200 - SEMINAR_CHAT_MIN_READING_PX - SEMINAR_TASK_RAIL_PX)
  })

  it('shrinks the document pane when the task drawer is open', () => {
    const closed = seminarDocPaneBudget(1200, { drawerOpen: false, reading: true })
    const open = seminarDocPaneBudget(1200, { drawerOpen: true, reading: true })
    expect(open).toBe(closed - SEMINAR_TASK_DRAWER_PX)
    expect(open).toBeLessThan(closed)
  })

  it('does not drop below the document minimum', () => {
    expect(seminarDocPaneBudget(400, { drawerOpen: true, reading: true })).toBe(320)
  })
})
