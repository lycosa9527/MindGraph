import { describe, expect, it } from 'vitest'

import {
  fallbackCapabilitiesForRole,
  roleHasPanelAccess,
  tabEditCapability,
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

  it('platform_bd has read-only global tabs plus invite edit', () => {
    const caps = fallbackCapabilitiesForRole('platform_bd')
    expect(caps).toContain('tab.data_center.view')
    expect(caps).toContain('tab.data_center.edit')
    expect(caps).toContain('tab.users.view')
    expect(caps).toContain('tab.organizations.view')
    expect(caps).toContain('tab.billing.view')
    expect(caps).toContain('tab.invites.view')
    expect(caps).toContain('tab.invites.edit')
    expect(caps).not.toContain('tab.users.edit')
    expect(caps).not.toContain('tab.organizations.edit')
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
    expect(roleHasPanelAccess('platform_bd')).toBe(true)
  })

  it('tabEditCapability maps admin tabs', () => {
    expect(tabEditCapability('invites')).toBe('tab.invites.edit')
    expect(tabEditCapability('users')).toBe('tab.users.edit')
  })
})
