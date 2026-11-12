import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearSeminarCustomRoles,
  rememberSeminarCustomRole,
  seminarCustomRoles,
  syncSeminarCustomRoles,
} from '@/utils/seminarCustomRoles'

describe('seminarCustomRoles', () => {
  beforeEach(() => {
    clearSeminarCustomRoles()
  })

  it('remembers free-text roles in the shared pool', () => {
    expect(rememberSeminarCustomRole('主讲老师')).toBe('主讲老师')
    expect(seminarCustomRoles.value).toEqual(['主讲老师'])
    expect(rememberSeminarCustomRole('主讲老师')).toBe('主讲老师')
    expect(seminarCustomRoles.value).toEqual(['主讲老师'])
  })

  it('ignores builtin roles', () => {
    expect(rememberSeminarCustomRole('observer')).toBeNull()
    expect(seminarCustomRoles.value).toEqual([])
  })

  it('syncs customs from a roster without wiping existing ones', () => {
    rememberSeminarCustomRole('记录员')
    syncSeminarCustomRoles(['observer', '点评嘉宾', 'leadPrep'])
    expect(seminarCustomRoles.value).toEqual(['记录员', '点评嘉宾'])
  })
})
