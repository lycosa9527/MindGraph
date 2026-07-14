/**
 * Canonical national data center (MG全国数据中心) lives in the admin panel.
 * Legacy `/dashboard` URLs redirect here.
 */
import type { RouteLocationNormalizedLoaded, RouteLocationRaw } from 'vue-router'

export const PUBLIC_DASHBOARD_ADMIN_QUERY = {
  tab: 'settings',
  subtab: 'public_dashboard',
} as const

export const PUBLIC_DASHBOARD_ADMIN_LOCATION: RouteLocationRaw = {
  path: '/admin',
  query: { ...PUBLIC_DASHBOARD_ADMIN_QUERY },
}

/** Absolute path+query for redirects and docs. */
export const PUBLIC_DASHBOARD_ADMIN_HREF =
  '/admin?tab=settings&subtab=public_dashboard'

export function isAdminPublicDashboardRoute(
  route: Pick<RouteLocationNormalizedLoaded, 'path' | 'query'>
): boolean {
  return (
    route.path === '/admin' &&
    route.query.tab === 'settings' &&
    route.query.subtab === 'public_dashboard'
  )
}
