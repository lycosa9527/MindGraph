import { describe, expect, it } from 'vitest'

import {
  applyCollabReadCursor,
  applyCollabReadCursorList,
  collabReadCursorFromFrame,
  collabReceiptState,
  formatCollabMessageStamp,
  readersForCollabMessage,
  sameCollabMessageMinute,
} from '@/utils/mindmateSeminarRead'

describe('mindmateSeminarRead', () => {
  const ada = {
    userId: 2,
    username: 'Ada',
    lastReadMessageId: 8,
    readAt: '2026-09-30T08:05:00.000Z',
  }
  const bea = {
    userId: 3,
    username: 'Bea',
    lastReadMessageId: 4,
    readAt: '2026-09-30T08:01:00.000Z',
  }

  it('keeps a newer cursor and ignores an older one for the same person', () => {
    const first = applyCollabReadCursor([], ada)
    const older = applyCollabReadCursor(first, { ...ada, lastReadMessageId: 3 })
    expect(older[0]?.lastReadMessageId).toBe(8)
    const newer = applyCollabReadCursor(older, { ...ada, lastReadMessageId: 11 })
    expect(newer).toHaveLength(1)
    expect(newer[0]?.lastReadMessageId).toBe(11)
  })

  it('lists other people who have read this line, not the sender', () => {
    const readers = readersForCollabMessage([ada, bea], 6, 9)
    expect(readers.map((row) => row.username)).toEqual(['Ada'])
    expect(readersForCollabMessage([ada], 6, ada.userId)).toEqual([])
    expect(collabReceiptState(undefined, 0)).toBe('sending')
    expect(collabReceiptState(6, 0)).toBe('sent')
    expect(collabReceiptState(6, 1)).toBe('read')
  })

  it('loads a join list from empty and keeps a person already on screen', () => {
    const joined = applyCollabReadCursorList(
      [],
      [
        { user_id: 2, username: 'Ada', last_read_message_id: 8, read_at: ada.readAt },
        { user_id: 'nope' },
      ]
    )
    expect(joined.map((row) => row.userId)).toEqual([2])
    const kept = applyCollabReadCursorList(
      [bea],
      [{ user_id: 2, username: 'Ada', last_read_message_id: 8, read_at: ada.readAt }]
    )
    expect(kept.map((row) => row.userId)).toEqual([3, 2])
    expect(collabReadCursorFromFrame({ user_id: 1.5, last_read_message_id: 2 })).toBeNull()
  })

  it('stamps today with the clock and an older day with the date', () => {
    const now = new Date('2026-09-30T08:00:00.000Z')
    expect(formatCollabMessageStamp('2026-09-30T08:05:00.000Z', now)).not.toContain('Sep')
    expect(formatCollabMessageStamp('2026-09-29T08:05:00.000Z', now).length).toBeGreaterThan(4)
    expect(formatCollabMessageStamp('')).toBe('')
  })

  it('treats two sends in one clock minute as the same stamp', () => {
    expect(sameCollabMessageMinute('2026-10-24T07:13:10.000Z', '2026-10-24T07:13:50.000Z')).toBe(
      true
    )
    expect(sameCollabMessageMinute('2026-10-24T07:13:50.000Z', '2026-10-24T07:14:01.000Z')).toBe(
      false
    )
    expect(sameCollabMessageMinute('2026-10-24T07:13:10.000Z', '2026-10-23T07:13:10.000Z')).toBe(
      false
    )
    expect(sameCollabMessageMinute('2026-10-24T07:13:10.000Z', undefined)).toBe(false)
    expect(sameCollabMessageMinute('not-a-time', '2026-10-24T07:13:10.000Z')).toBe(false)
  })
})
