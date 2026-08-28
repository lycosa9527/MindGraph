import { describe, expect, it } from 'vitest'

import {
  formatMindmateCollabCode,
  mergeMindmateCollabSessionLists,
  normalizeMindmateCollabCode,
} from '@/utils/mindmateCollabSessions'

function isActiveRoute(routeCode: string | null, sessionCode: string): boolean {
  if (!routeCode) return false
  return normalizeMindmateCollabCode(routeCode) === normalizeMindmateCollabCode(sessionCode)
}

describe('MindmateCollabHistory helpers', () => {
  it('highlights active row when codes match with dash variants', () => {
    expect(isActiveRoute('ABC-DEF', 'ABCDEF')).toBe(true)
    expect(isActiveRoute('ABC-DEF', 'XYZ-123')).toBe(false)
  })

  it('formats code for navigation query', () => {
    expect(formatMindmateCollabCode('abcdef')).toBe('ABC-DEF')
  })

  it('keeps a colleague org room in the sidebar group list', () => {
    const merged = mergeMindmateCollabSessionLists(
      [{ code: '8KZ-BAW', title: '王寸尺 seminar', owner_user_id: 3 }],
      [{ code: 'GJR-42J', title: 'My hosted', owner_user_id: 5 }],
    )
    const codes = merged.map((row) => normalizeMindmateCollabCode(row.code)).sort()
    expect(codes).toEqual(['8KZBAW', 'GJR42J'])
  })
})
