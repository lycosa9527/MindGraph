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

  it('keeps the current thinking bubble when a peer kitty turn is for another request', () => {
    const existing = [
      { id: 'u1', role: 'user' as const, text: '加分支', requestId: 'r-new' },
      { id: 'think', role: 'kitty' as const, text: '正在思考…', thinking: true },
    ]
    const next = mergeKittyConversationTurn(
      existing,
      { turn_id: 'k-old', role: 'kitty', content: '已加上', request_id: 'r-old' },
      'fallback'
    )
    expect(next?.some((row) => row.thinking)).toBe(true)
    expect(next?.map((row) => row.id)).toEqual(['u1', 'think', 'k-old'])
  })

  it('drops thinking when the merged kitty turn finishes the current request', () => {
    const existing = [
      { id: 'u1', role: 'user' as const, text: '加分支', requestId: 'r1' },
      { id: 'think', role: 'kitty' as const, text: '正在思考…', thinking: true },
    ]
    const next = mergeKittyConversationTurn(
      existing,
      { turn_id: 'k1', role: 'kitty', content: '好，加上了。', request_id: 'r1' },
      'fallback'
    )
    expect(next?.some((row) => row.thinking)).toBe(false)
    expect(next?.map((row) => row.text)).toEqual(['加分支', '好，加上了。'])
  })
})
