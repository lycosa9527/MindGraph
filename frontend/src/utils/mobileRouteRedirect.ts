/**
 * Mobile auto-redirect targets when a touch/small-viewport client hits desktop routes.
 */
const MOBILE_ROUTE_MAP: Record<string, string> = {
  '/': '/m',
  '/mindmate': '/m/mindmate',
  '/mindgraph': '/m/mindgraph',
  '/canvas': '/m/canvas',
}

const MOBILE_REDIRECT_SKIP_PREFIXES = [
  '/login',
  '/auth',
  '/privacy',
  '/bayi/passkey',
  '/export-render',
  '/dashboard',
  '/admin',
] as const

/** Destination under `/m/*`, or hub `/m` for unmapped desktop paths. */
export function resolveMobileRouteRedirect(desktopPath: string): string {
  return MOBILE_ROUTE_MAP[desktopPath] ?? '/m'
}

export function isMobileRoutePath(path: string): boolean {
  return path === '/m' || path.startsWith('/m/')
}

export function shouldSkipMobileRouteRedirect(path: string): boolean {
  if (isMobileRoutePath(path)) {
    return true
  }
  return MOBILE_REDIRECT_SKIP_PREFIXES.some(
    (prefix) => path === prefix || path.startsWith(`${prefix}/`)
  )
}
