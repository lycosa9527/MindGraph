import { describe, expect, it } from 'vitest'

import { applyDeletedChatMessage, applyEditedChatMessage } from '@/utils/workshopMessageLocalPatch'

describe('workshopMessageLocalPatch', () => {
  it('updates content and edited_at in place', () => {
    const messages = [{ id: 3, content: 'old', edited_at: null as string | null }]
    applyEditedChatMessage(messages, {
      id: 3,
      content: 'new',
      edited_at: '2026-09-07T01:00:00Z',
    })
    expect(messages[0].content).toBe('new')
    expect(messages[0].edited_at).toBe('2026-09-07T01:00:00Z')
  })

  it('marks a row deleted without removing it', () => {
    const messages = [{ id: 8, content: 'gone', is_deleted: false }]
    applyDeletedChatMessage(messages, 8)
    expect(messages).toHaveLength(1)
    expect(messages[0].is_deleted).toBe(true)
    expect(messages[0].content).toBe('')
  })
})
