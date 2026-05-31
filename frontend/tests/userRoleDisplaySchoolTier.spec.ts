import { describe, expect, it } from 'vitest'

import { getRolePillStyle } from '@/utils/userRoleDisplay'

describe('getRolePillStyle with school tier', () => {
  it('shows trial edition pill for teachers in trial orgs only', () => {
    expect(getRolePillStyle('teacher', 'trial')?.labelKey).toBe('sidebar.roleTrialEdition')
  })

  it('keeps school admin label in trial orgs', () => {
    expect(getRolePillStyle('school_admin', 'trial')?.labelKey).toBe(
      'sidebar.roleSchoolAdmin'
    )
  })

  it('shows school edition pill for teachers in paid tiers', () => {
    expect(getRolePillStyle('teacher', 'lite')?.labelKey).toBe('sidebar.roleSchoolEdition')
    expect(getRolePillStyle('teacher', 'standard')?.labelKey).toBe('sidebar.roleSchoolEdition')
    expect(getRolePillStyle('teacher', 'professional')?.labelKey).toBe(
      'sidebar.roleSchoolEdition'
    )
  })

  it('keeps school admin label in paid tiers', () => {
    expect(getRolePillStyle('school_admin', 'standard')?.labelKey).toBe(
      'sidebar.roleSchoolAdmin'
    )
  })

  it('does not override platform roles with school tier', () => {
    expect(getRolePillStyle('superadmin', 'trial')?.labelKey).toBe('sidebar.roleSuperAdmin')
    expect(getRolePillStyle('personal_trial', 'trial')?.labelKey).toBe('sidebar.roleTrialEdition')
  })

  it('falls back to role-only pills when school tier is omitted', () => {
    expect(getRolePillStyle('teacher')?.labelKey).toBe('sidebar.roleSchoolEdition')
  })
})
