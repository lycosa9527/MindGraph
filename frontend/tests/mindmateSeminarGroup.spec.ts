import { describe, expect, it } from 'vitest'

import { type SeminarGroupMember, briefCardPeopleFromMembers } from '@/utils/mindmateSeminarGroup'

const labels = {
  roleLabel: (role: string) => {
    if (role === 'leader') return '组长'
    if (role === 'observer') return '观摩学习'
    if (role === 'researcher') return '教研员'
    return role
  },
  pendingConsent: '待对方同意',
}

function member(
  partial: Partial<SeminarGroupMember> & { userId: number; name: string }
): SeminarGroupMember {
  return {
    avatar: null,
    role: 'observer',
    online: false,
    isOwner: false,
    isLeader: false,
    pending: false,
    lastSeenAt: null,
    organizationId: null,
    organizationName: null,
    ...partial,
  }
}

describe('briefCardPeopleFromMembers', () => {
  it('puts the leader first and uses live roles instead of the start snapshot', () => {
    const people = briefCardPeopleFromMembers(
      [
        member({ userId: 2, name: '方健姣', role: 'observer' }),
        member({ userId: 1, name: '吴浪松', role: 'leader', isLeader: true, isOwner: true }),
        member({ userId: 3, name: '上官建萍', role: 'researcher', pending: true }),
      ],
      labels
    )
    expect(people[0]).toEqual({ name: '吴浪松', role: '组长' })
    expect(people).toContainEqual({ name: '上官建萍', role: '教研员 · 待对方同意' })
    expect(people).toContainEqual({ name: '方健姣', role: '观摩学习' })
    expect(people).toHaveLength(3)
  })
})
