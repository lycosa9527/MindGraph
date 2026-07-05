import { describe, expect, it } from 'vitest'

import {
  mindmateCollabDisconnectShouldNotify,
  mindmateCollabWsErrorLocaleKey,
  mindmateCollabWsErrorRollsBackSend,
} from '@/utils/mindmateCollabWsErrors'

describe('mindmateCollabWsErrorLocaleKey', () => {
  it('maps known server error codes', () => {
    expect(mindmateCollabWsErrorLocaleKey('room_closed')).toBe('mindmate.collabErrorRoomClosed')
    expect(mindmateCollabWsErrorLocaleKey('dify_error')).toBe('mindmate.collabErrorDify')
  })

  it('returns null for unknown codes', () => {
    expect(mindmateCollabWsErrorLocaleKey('unknown')).toBeNull()
  })
})

describe('mindmateCollabWsErrorRollsBackSend', () => {
  it('rolls back when the server rejected before persist', () => {
    expect(mindmateCollabWsErrorRollsBackSend('room_closed')).toBe(true)
    expect(mindmateCollabWsErrorRollsBackSend('rate_limit')).toBe(true)
  })

  it('keeps message when AI is busy', () => {
    expect(mindmateCollabWsErrorRollsBackSend('mindmate_responding')).toBe(false)
  })
})

describe('mindmateCollabDisconnectShouldNotify', () => {
  it('suppresses lifecycle close codes', () => {
    expect(mindmateCollabDisconnectShouldNotify(4010, false, false)).toBe('none')
    expect(mindmateCollabDisconnectShouldNotify(4011, false, false)).toBe('none')
    expect(mindmateCollabDisconnectShouldNotify(4003, false, false)).toBe('none')
  })

  it('signals reconnect exhaustion', () => {
    expect(mindmateCollabDisconnectShouldNotify(1006, false, true)).toBe('reconnect_failed')
  })
})
