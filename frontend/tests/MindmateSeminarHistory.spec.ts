import { describe, expect, it } from 'vitest'

import {
  formatMindmateSeminarCode,
  mergeMindmateSeminarSessionLists,
  normalizeMindmateSeminarCode,
} from '@/utils/mindmateSeminarSessions'

function isActiveRoute(routeCode: string | null, sessionCode: string): boolean {
  if (!routeCode) return false
  return normalizeMindmateSeminarCode(routeCode) === normalizeMindmateSeminarCode(sessionCode)
}

describe('MindmateSeminarHistory helpers', () => {
  it('highlights active row when codes match with dash variants', () => {
    expect(isActiveRoute('ABC-DEF', 'ABCDEF')).toBe(true)
    expect(isActiveRoute('ABC-DEF', 'XYZ-123')).toBe(false)
  })

  it('formats code for navigation query', () => {
    expect(formatMindmateSeminarCode('abcdef')).toBe('ABC-DEF')
  })

  it('keeps a colleague org room in the sidebar group list', () => {
    const merged = mergeMindmateSeminarSessionLists(
      [{ code: '8KZ-BAW', title: '王寸尺 seminar', owner_user_id: 3 }],
      [{ code: 'GJR-42J', title: 'My hosted', owner_user_id: 5 }]
    )
    const codes = merged.map((row) => normalizeMindmateSeminarCode(row.code)).sort()
    expect(codes).toEqual(['8KZBAW', 'GJR42J'])
  })
})
