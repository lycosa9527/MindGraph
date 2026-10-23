import { describe, expect, it } from 'vitest'

import { mindmateStreamNoticeKey } from '@/utils/mindmateStreamErrorNotice'

const base = { onBackup: false, hasPartial: false, emptyStream: false }

describe('mindmateStreamNoticeKey', () => {
  it('names a main-server outage and a backup failure separately', () => {
    expect(mindmateStreamNoticeKey('gateway', 'dify_main_unavailable', base)).toBe(
      'mindmate.mainServerDownRetry'
    )
    expect(
      mindmateStreamNoticeKey('gateway', 'dify_backup_unavailable', { ...base, onBackup: true })
    ).toBe('mindmate.backupServerFailed')
    expect(mindmateStreamNoticeKey('HTTP error! status: 503', undefined, base)).toBe(
      'mindmate.mainServerDownRetry'
    )
  })

  it('keeps coin and other specific server text', () => {
    expect(
      mindmateStreamNoticeKey('思维币不足', 'thinking_coin_insufficient', base)
    ).toBeNull()
    expect(mindmateStreamNoticeKey('对话不存在', undefined, base)).toBeNull()
  })

  it('splits network, cut-off, empty, and our own server errors', () => {
    expect(mindmateStreamNoticeKey('Failed to fetch', undefined, base)).toBe(
      'mindmate.networkRetry'
    )
    expect(
      mindmateStreamNoticeKey('Failed to fetch', undefined, { ...base, hasPartial: true })
    ).toBe('mindmate.replyCutOff')
    expect(mindmateStreamNoticeKey(undefined, 'internal_error', base)).toBe(
      'mindmate.serviceRetry'
    )
    expect(mindmateStreamNoticeKey(undefined, undefined, { ...base, emptyStream: true })).toBe(
      'mindmate.noReply'
    )
    expect(
      mindmateStreamNoticeKey(undefined, undefined, {
        ...base,
        emptyStream: true,
        onBackup: true,
      })
    ).toBe('mindmate.backupServerFailed')
  })
})
