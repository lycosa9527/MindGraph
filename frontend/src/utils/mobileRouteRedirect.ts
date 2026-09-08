/**
 * Mobile auto-redirect targets when a touch/small-viewport client hits desktop routes.
 */
const MOBILE_ROUTE_MAP: Record<string, string> = {
  '/': '/m',
  '/mindmate': '/m/mindmate',
  '/mindgraph': '/m/mindgraph',
  '/canvas': '/m/canvas',
  '/voice-notes': '/m/voice-notes',
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

export function resolveMobileRouteRedirect(
  desktopPath: string,
  opts?: { isTrainingLead?: boolean }
): string {
  if (desktopPath === '/training') {
    return opts?.isTrainingLead ? '/m/training' : '/m'
  }
  if (desktopPath.startsWith('/training/')) {
    return '/m'
  }
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
