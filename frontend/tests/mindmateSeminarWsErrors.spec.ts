import { describe, expect, it } from 'vitest'

import {
  mindmateSeminarDisconnectShouldNotify,
  mindmateSeminarWsErrorLocaleKey,
  mindmateSeminarWsErrorRollsBackSend,
} from '@/utils/mindmateSeminarWsErrors'

describe('mindmateSeminarWsErrorLocaleKey', () => {
  it('maps known server error codes', () => {
    expect(mindmateSeminarWsErrorLocaleKey('room_closed')).toBe('mindmate.collabErrorRoomClosed')
    expect(mindmateSeminarWsErrorLocaleKey('dify_error')).toBe('mindmate.collabErrorDify')
    expect(mindmateSeminarWsErrorLocaleKey('dify_main_unavailable')).toBe(
      'mindmate.mainServerDownRetry'
    )
    expect(mindmateSeminarWsErrorLocaleKey('dify_backup_unavailable')).toBe(
      'mindmate.backupServerFailed'
    )
  })

  it('returns null for unknown codes', () => {
    expect(mindmateSeminarWsErrorLocaleKey('unknown')).toBeNull()
  })
})

describe('mindmateSeminarWsErrorRollsBackSend', () => {
  it('rolls back when the server rejected before persist', () => {
    expect(mindmateSeminarWsErrorRollsBackSend('room_closed')).toBe(true)
    expect(mindmateSeminarWsErrorRollsBackSend('rate_limit')).toBe(true)
  })

  it('keeps message when AI is busy', () => {
    expect(mindmateSeminarWsErrorRollsBackSend('mindmate_responding')).toBe(false)
  })
})

describe('mindmateSeminarDisconnectShouldNotify', () => {
  it('suppresses lifecycle close codes', () => {
    expect(mindmateSeminarDisconnectShouldNotify(4010, false, false)).toBe('none')
    expect(mindmateSeminarDisconnectShouldNotify(4011, false, false)).toBe('none')
    expect(mindmateSeminarDisconnectShouldNotify(4003, false, false)).toBe('none')
  })

  it('signals reconnect exhaustion', () => {
    expect(mindmateSeminarDisconnectShouldNotify(1006, false, true)).toBe('reconnect_failed')
  })
})
