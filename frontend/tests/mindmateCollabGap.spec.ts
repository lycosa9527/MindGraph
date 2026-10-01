import { describe, expect, it } from 'vitest'

import {
  collabChainNeedsFill,
  collabCursorBehind,
  collabGapAfterId,
  collabMaxSavedId,
  collabPrevId,
  collabSnapshotBackfillAfterId,
  collabTranscriptBehind,
  insertMissingCollabMessages,
  streamingCoveredBySaved,
} from '@/utils/mindmateCollabGap'

describe('mindmateCollabGap', () => {
  it('asks for missing lines only when the previous id is absent', () => {
    const messages = [{ id: 2, role: 'user' as const, content: 'kept' }]
    expect(collabChainNeedsFill(messages, null)).toBe(false)
    expect(collabChainNeedsFill(messages, 2)).toBe(false)
    expect(collabChainNeedsFill(messages, 4)).toBe(true)
    expect(collabPrevId('4')).toBeNull()
    expect(collabPrevId(4)).toBe(4)
  })

  it('fills the hole in id order and leaves the unsent bubble at the end', () => {
    const optimistic = { role: 'user' as const, content: 'typing', clientKey: 'local-1' }
    const merged = insertMissingCollabMessages(
      [
        { id: 2, role: 'user' as const, content: 'kept' },
        { id: 6, role: 'user' as const, content: 'later' },
        optimistic,
      ],
      [
        { id: 4, role: 'user' as const, content: 'missed' },
        { id: 6, role: 'user' as const, content: 'later' },
      ]
    )
    expect(merged.map((row) => row.id ?? row.content)).toEqual([2, 4, 6, 'typing'])
    expect(merged[3]).toBe(optimistic)
    expect(collabGapAfterId(merged, 4)).toBe(2)
  })

  it('replaces an unsent bubble when the saved copy arrives', () => {
    const merged = insertMissingCollabMessages(
      [
        {
          role: 'user' as const,
          content: 'hello',
          sender_user_id: 3,
          clientKey: 'local-1',
        },
      ],
      [{ id: 9, role: 'user' as const, content: 'hello', sender_user_id: 3 }]
    )
    expect(merged).toEqual([{ id: 9, role: 'user', content: 'hello', sender_user_id: 3 }])
  })

  it('loads the hole between a saved cursor and a later snapshot', () => {
    const current = [{ id: 4 }, { id: 9 }]
    expect(collabMaxSavedId(current)).toBe(9)
    expect(collabCursorBehind(current, 9)).toBe(false)
    expect(collabCursorBehind(current, 12)).toBe(true)
    expect(collabTranscriptBehind(current, 9)).toBe(false)
    expect(collabTranscriptBehind(current, 12)).toBe(true)
    expect(collabTranscriptBehind(current, null)).toBe(false)
    expect(collabSnapshotBackfillAfterId(9, [{ id: 20 }, { id: 21 }])).toBe(9)
    expect(collabSnapshotBackfillAfterId(21, [{ id: 20 }])).toBeNull()
    expect(collabSnapshotBackfillAfterId(0, [{ id: 20 }])).toBeNull()
  })

  it('treats a saved assistant reply as covering the live stream prefix', () => {
    expect(streamingCoveredBySaved('Hel', [{ id: 3, role: 'assistant', content: 'Hello' }])).toBe(
      true
    )
    expect(streamingCoveredBySaved('Hello', [{ id: 3, role: 'user', content: 'Hello' }])).toBe(
      false
    )
  })
})
