import { describe, expect, it } from 'vitest'

import {
  canViewDataCenterTab,
  canViewUsersTab,
  fallbackCapabilitiesForRole,
  roleHasPanelAccess,
  tabEditCapability,
  tabRequiresCapabilities,
} from '@/utils/adminCapabilities'
import { visibleDataCenterViews } from '@/composables/admin/adminDataCenterViews'

describe('adminCapabilities', () => {
  it('school_admin can view school dashboard and users caps only', () => {
    const caps = fallbackCapabilitiesForRole('school_admin')
    expect(caps).toContain('tab.school_dashboard.view')
    expect(caps).toContain('tab.users.view')
    expect(caps).not.toContain('tab.data_center.view')
    expect(caps).not.toContain('tab.organizations.view')
    expect(caps).not.toContain('tab.invites.view')
    expect(caps).not.toContain('tab.settings.view')
    expect(visibleDataCenterViews(caps)).toEqual(['school_dashboard'])
  })

  it('teacher has no panel capabilities', () => {
    expect(fallbackCapabilitiesForRole('teacher')).toEqual([])
  })

  it('platform_bd has read-only global tabs plus invite edit', () => {
    const caps = fallbackCapabilitiesForRole('platform_bd')
    expect(caps).toContain('tab.data_center.view')
    expect(caps).toContain('tab.data_center.edit')
    expect(caps).toContain('tab.school_dashboard.view')
    expect(caps).toContain('tab.users.view')
    expect(caps).toContain('tab.organizations.view')
    expect(caps).toContain('tab.billing.view')
    expect(caps).toContain('tab.invites.view')
    expect(caps).toContain('tab.invites.edit')
    expect(caps).toContain('scope.global')
    expect(caps).toContain('scope.invited_orgs')
    expect(caps).not.toContain('tab.users.edit')
    expect(caps).not.toContain('tab.organizations.edit')
  })

  it('expert has invites and invited-org scope only', () => {
    const caps = fallbackCapabilitiesForRole('expert')
    expect(caps).toContain('tab.invites.view')
    expect(caps).toContain('tab.invites.edit')
    expect(caps).toContain('scope.invited_orgs')
    expect(caps).not.toContain('tab.data_center.view')
  })

  it('roleHasPanelAccess matches panel roles only', () => {
    expect(roleHasPanelAccess('teacher')).toBe(false)
    expect(roleHasPanelAccess('school_admin')).toBe(true)
    expect(roleHasPanelAccess('expert')).toBe(true)
    expect(roleHasPanelAccess('platform_bd')).toBe(true)
  })

  it('canViewDataCenterTab accepts school dashboard cap alone', () => {
    expect(canViewDataCenterTab(['tab.school_dashboard.view'])).toBe(true)
    expect(canViewDataCenterTab(['tab.data_center.view'])).toBe(true)
    expect(canViewDataCenterTab(['tab.users.view'])).toBe(false)
  })

  it('tabEditCapability maps admin tabs', () => {
    expect(tabEditCapability('invites')).toBe('tab.invites.edit')
    expect(tabEditCapability('users')).toBe('tab.users.edit')
  })

  it('data_center tab requires no fixed caps (checked via canViewDataCenterTab)', () => {
    expect(tabRequiresCapabilities('data_center')).toEqual([])
  })

  it('canViewUsersTab requires global scope', () => {
    expect(canViewUsersTab(['tab.users.view', 'scope.global'])).toBe(true)
    expect(canViewUsersTab(['tab.users.view', 'scope.org'])).toBe(false)
  })
})
