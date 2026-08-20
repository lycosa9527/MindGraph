import { describe, expect, it } from 'vitest'

import { visibleDataCenterViews } from '@/composables/admin/adminDataCenterViews'
import {
  canManageOrganizationsOnMobile,
  canSeeMobileOrgManagement,
  canViewDataCenterTab,
  canViewUsersTab,
  fallbackCapabilitiesForRole,
  hasSuperadminPanelAccess,
  isDataCenterTabReadOnly,
  roleHasPanelAccess,
  settingsSubtabRequiresCapabilities,
  tabEditCapability,
  tabRequiresCapabilities,
} from '@/utils/adminCapabilities'

describe('adminCapabilities', () => {
  it('superadmin can edit organizations and settings', () => {
    const caps = fallbackCapabilitiesForRole('superadmin')
    expect(caps).toContain('tab.organizations.view')
    expect(caps).toContain('tab.organizations.edit')
    expect(hasSuperadminPanelAccess(caps)).toBe(true)
  })

  it('school_admin can view school dashboard and users caps only', () => {
    const caps = fallbackCapabilitiesForRole('school_admin')
    expect(caps).toContain('tab.school_dashboard.view')
    expect(caps).toContain('tab.users.view')
    expect(caps).not.toContain('tab.data_center.view')
    expect(caps).not.toContain('tab.organizations.view')
    expect(caps).not.toContain('tab.invites.view')
    expect(caps).not.toContain('tab.settings.view')
    expect(caps).not.toContain('tab.settings.mindmate_export')
    expect(visibleDataCenterViews(caps)).toEqual(['school_dashboard'])
    expect(isDataCenterTabReadOnly(caps)).toBe(false)
  })

  it('teacher has no panel capabilities', () => {
    expect(fallbackCapabilitiesForRole('teacher')).toEqual([])
  })

  it('platform_bd has read-only global tabs plus invite edit', () => {
    const caps = fallbackCapabilitiesForRole('platform_bd')
    expect(isDataCenterTabReadOnly(caps)).toBe(false)
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

  it('expert has organizations view, invites, and invited-org scope only', () => {
    const caps = fallbackCapabilitiesForRole('expert')
    expect(caps).toContain('tab.organizations.view')
    expect(caps).toContain('tab.invites.view')
    expect(caps).toContain('tab.invites.edit')
    expect(caps).toContain('scope.invited_orgs')
    expect(caps).not.toContain('tab.organizations.edit')
    expect(caps).not.toContain('scope.global')
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

  it('thinking_coins settings subtab maps to dedicated capability', () => {
    expect(settingsSubtabRequiresCapabilities('thinking_coins')).toEqual([
      'tab.settings.thinking_coins',
    ])
  })

  it('canSeeMobileOrgManagement hides the card until API caps load', () => {
    expect(canSeeMobileOrgManagement(null, false)).toBe(false)
    expect(canSeeMobileOrgManagement(null, true)).toBe(false)
    expect(
      canSeeMobileOrgManagement(
        {
          role: 'teacher',
          capabilities: [],
          org_ids: null,
          read_only: false,
          default_org_id: null,
          panel_access: false,
        },
        true
      )
    ).toBe(false)
    expect(
      canSeeMobileOrgManagement(
        {
          role: 'school_admin',
          capabilities: fallbackCapabilitiesForRole('school_admin'),
          org_ids: [1],
          read_only: false,
          default_org_id: 1,
          panel_access: true,
        },
        true
      )
    ).toBe(false)
    expect(
      canSeeMobileOrgManagement(
        {
          role: 'expert',
          capabilities: fallbackCapabilitiesForRole('expert'),
          org_ids: [],
          read_only: false,
          default_org_id: null,
          panel_access: true,
        },
        true
      )
    ).toBe(true)
    expect(
      canSeeMobileOrgManagement(
        {
          role: 'superadmin',
          capabilities: fallbackCapabilitiesForRole('superadmin'),
          org_ids: null,
          read_only: false,
          default_org_id: null,
          panel_access: true,
        },
        true
      )
    ).toBe(true)
  })

  it('canManageOrganizationsOnMobile allows create-org roles only', () => {
    expect(canManageOrganizationsOnMobile(fallbackCapabilitiesForRole('superadmin'))).toBe(true)
    expect(canManageOrganizationsOnMobile(fallbackCapabilitiesForRole('expert'))).toBe(true)
    expect(canManageOrganizationsOnMobile(fallbackCapabilitiesForRole('platform_bd'))).toBe(true)
    expect(canManageOrganizationsOnMobile(fallbackCapabilitiesForRole('school_admin'))).toBe(false)
    expect(canManageOrganizationsOnMobile(fallbackCapabilitiesForRole('teacher'))).toBe(false)
  })

  it('public_dashboard settings subtab is superadmin-only', () => {
    expect(settingsSubtabRequiresCapabilities('public_dashboard')).toEqual([
      'tab.settings.public_dashboard',
    ])
    expect(fallbackCapabilitiesForRole('superadmin')).toContain('tab.settings.public_dashboard')
    for (const role of [
      'platform_bd',
      'expert',
      'school_admin',
      'teacher',
      'personal_trial',
      'personal_paid',
    ] as const) {
      expect(fallbackCapabilitiesForRole(role)).not.toContain('tab.settings.public_dashboard')
    }
  })
})
