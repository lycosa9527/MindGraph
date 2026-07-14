import { describe, expect, it } from 'vitest'

import {
  PUBLIC_DASHBOARD_ADMIN_HREF,
  PUBLIC_DASHBOARD_ADMIN_LOCATION,
  isAdminPublicDashboardRoute,
} from '@/utils/publicDashboardRoute'

describe('publicDashboardRoute', () => {
  it('exposes the canonical admin location', () => {
    expect(PUBLIC_DASHBOARD_ADMIN_HREF).toBe('/admin?tab=settings&subtab=public_dashboard')
    expect(PUBLIC_DASHBOARD_ADMIN_LOCATION).toEqual({
      path: '/admin',
      query: { tab: 'settings', subtab: 'public_dashboard' },
    })
  })

  it('detects the admin national dashboard route', () => {
    expect(
      isAdminPublicDashboardRoute({
        path: '/admin',
        query: { tab: 'settings', subtab: 'public_dashboard' },
      })
    ).toBe(true)
  })

  it('rejects other admin tabs and non-admin paths', () => {
    expect(
      isAdminPublicDashboardRoute({
        path: '/admin',
        query: { tab: 'settings', subtab: 'roles' },
      })
    ).toBe(false)
    expect(
      isAdminPublicDashboardRoute({
        path: '/admin',
        query: { tab: 'users' },
      })
    ).toBe(false)
    expect(
      isAdminPublicDashboardRoute({
        path: '/dashboard',
        query: {},
      })
    ).toBe(false)
  })
})
