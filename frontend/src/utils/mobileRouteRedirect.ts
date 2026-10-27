/**
 * Mobile auto-redirect targets when a touch/small-viewport client hits desktop routes.
 */
const MOBILE_ROUTE_MAP: Record<string, string> = {
  '/': '/m',
  '/mindmate': '/m/mindmate',
  '/mindgraph': '/m/mindgraph',
  '/canvas': '/m/canvas',
  '/voice-notes': '/m/voice-notes',
  '/learning-space': '/m/learning-space',
}

const MOBILE_REDIRECT_SKIP_PREFIXES = [
  '/login',
  '/auth',
  '/privacy',
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

/** Desktop page for a mobile route when this device is locked to the desktop shell. */
const DESKTOP_SHELL_PATHS: Record<string, string> = {
  '/m': '/mindmate',
  '/m/mindmate': '/mindmate',
  '/m/mindgraph': '/mindgraph',
  '/m/canvas': '/canvas',
  '/m/voice-notes': '/voice-notes',
  '/m/learning-space': '/learning-space',
  '/m/training': '/training',
  '/m/kitty': '/mindmate',
  '/m/account': '/mindmate',
  '/m/orgs': '/mindmate',
}

/**
 * Route to open when a locked shell disagrees with the current path.
 * Returns null when the path already matches, or when the page stays put (admin, auth).
 */
export function pathForLockedClientShell(
  path: string,
  shell: 'mobile' | 'desktop',
  opts?: { isTrainingLead?: boolean }
): string | null {
  if (shell === 'desktop') {
    if (!isMobileRoutePath(path)) return null
    return DESKTOP_SHELL_PATHS[path] ?? '/mindmate'
  }
  if (isMobileRoutePath(path) || shouldSkipMobileRouteRedirect(path)) return null
  const target = resolveMobileRouteRedirect(path, opts)
  return target === path ? null : target
}
