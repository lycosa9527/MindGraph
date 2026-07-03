import { describe, expect, it } from 'vitest'

import {
  formatMindmateCollabCode,
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
})
