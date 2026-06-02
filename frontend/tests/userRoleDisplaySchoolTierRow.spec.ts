import { describe, expect, it } from 'vitest'

import { schoolTierFromUserRow, userRolePillView } from '@/utils/userRoleDisplay'

describe('schoolTierFromUserRow', () => {
  it('returns trial tier from list row payload', () => {
    expect(schoolTierFromUserRow({ school_tier: 'trial' })).toBe('trial')
  })

  it('returns undefined when tier is absent', () => {
    expect(schoolTierFromUserRow({})).toBeUndefined()
  })
})

describe('userRolePillView with school tier row', () => {
  const translate = (key: string) => key

  it('shows trial edition pill for teachers in trial org rows', () => {
    const pill = userRolePillView(translate, 'teacher', schoolTierFromUserRow({ school_tier: 'trial' }))
    expect(pill?.label).toBe('sidebar.roleTrialEdition')
  })
})
