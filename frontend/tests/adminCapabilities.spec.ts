import { describe, expect, it } from 'vitest'

import {
  fallbackCapabilitiesForRole,
  roleHasPanelAccess,
  tabRequiresCapabilities,
} from '@/utils/adminCapabilities'

describe('adminCapabilities', () => {
  it('school_admin can view data center and users', () => {
    const caps = fallbackCapabilitiesForRole('school_admin')
    expect(caps).toContain('tab.data_center.view')
    expect(caps).toContain('tab.users.view')
    expect(caps).not.toContain('tab.organizations.view')
  })

  it('teacher has no panel capabilities', () => {
    expect(fallbackCapabilitiesForRole('teacher')).toEqual([])
  })

  it('platform_bd has data center and invites only', () => {
    const caps = fallbackCapabilitiesForRole('platform_bd')
    expect(caps).toContain('tab.data_center.view')
    expect(caps).toContain('tab.invites.view')
    expect(caps).not.toContain('tab.users.view')
  })

  it('expert has invites only', () => {
    const caps = fallbackCapabilitiesForRole('expert')
    expect(caps).toContain('tab.invites.view')
    expect(caps).not.toContain('tab.data_center.view')
  })

  it('roleHasPanelAccess matches panel roles only', () => {
    expect(roleHasPanelAccess('teacher')).toBe(false)
    expect(roleHasPanelAccess('school_admin')).toBe(true)
    expect(roleHasPanelAccess('expert')).toBe(true)
  })
})
