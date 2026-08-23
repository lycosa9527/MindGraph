import { afterEach, describe, expect, it } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import {
  SCHOOL_EXPIRED_CODE,
  emitSchoolExpiredFromPayload,
  isSchoolExpiredPayload,
  parseSchoolExpiredPayload,
  resetSchoolExpiredLockoutEmit,
} from '@/utils/schoolExpiredLockout'

describe('schoolExpiredLockout', () => {
  afterEach(() => {
    resetSchoolExpiredLockoutEmit()
    eventBus.clear('auth:school_expired')
  })

  it('parses structured FastAPI detail', () => {
    const info = parseSchoolExpiredPayload({
      detail: {
        code: SCHOOL_EXPIRED_CODE,
        message: 'Your school subscription (Demo) expired on 2026-01-01.',
        school_name: 'Demo',
        expires_at: '2026-01-01',
      },
    })
    expect(info).toEqual({
      schoolName: 'Demo',
      expiresAt: '2026-01-01',
      message: 'Your school subscription (Demo) expired on 2026-01-01.',
    })
  })

  it('parses localized Chinese login copy', () => {
    expect(
      isSchoolExpiredPayload({
        detail: '您的学校订阅（示范中学）已于 2026-01-01 到期。教师与学校管理员均已锁定。',
      })
    ).toBe(true)
  })

  it('ignores unrelated 403 payloads', () => {
    expect(isSchoolExpiredPayload({ detail: 'Organization account is locked.' })).toBe(false)
    expect(isSchoolExpiredPayload({ detail: { code: 'organization_locked' } })).toBe(false)
    expect(isSchoolExpiredPayload(null)).toBe(false)
  })

  it('emits the lockout event once per session', () => {
    const seen: string[] = []
    eventBus.on('auth:school_expired', (info) => {
      seen.push(info.schoolName)
    })
    const payload = {
      detail: {
        code: SCHOOL_EXPIRED_CODE,
        school_name: 'East High',
        expires_at: '2026-08-01',
        message: 'expired',
      },
    }
    expect(emitSchoolExpiredFromPayload(payload)).toBe(true)
    expect(emitSchoolExpiredFromPayload(payload)).toBe(true)
    expect(seen).toEqual(['East High'])
  })
})
