import { describe, expect, it } from 'vitest'

import { mergeKittyConversationTurn } from '@/composables/kitty/applyKittyConversationTurn'

describe('applyKittyConversationTurn', () => {
  it('appends a peer kitty turn', () => {
    const next = mergeKittyConversationTurn(
      [],
      { turn_id: 't1', role: 'kitty', content: '已加上', request_id: 'r1' },
      'fallback'
    )
    expect(next).toEqual([
      expect.objectContaining({ id: 't1', role: 'kitty', text: '已加上', requestId: 'r1' }),
    ])
  })

  it('skips a duplicate turn_id', () => {
    const existing = [{ id: 't1', role: 'user' as const, text: '加分支', requestId: 'r1' }]
    expect(
      mergeKittyConversationTurn(
        existing,
        { turn_id: 't1', role: 'user', content: '加分支', request_id: 'r1' },
        'fallback'
      )
    ).toBeNull()
  })
})
