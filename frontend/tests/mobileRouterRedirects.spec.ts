import { describe, expect, it } from 'vitest'

import {
  isMobileRoutePath,
  pathForLockedClientShell,
  resolveMobileRouteRedirect,
  shouldSkipMobileRouteRedirect,
} from '@/utils/mobileRouteRedirect'

describe('mobileRouteRedirect', () => {
  it('maps desktop paths to mobile equivalents', () => {
    expect(resolveMobileRouteRedirect('/mindmate')).toBe('/m/mindmate')
    expect(resolveMobileRouteRedirect('/mindgraph')).toBe('/m/mindgraph')
    expect(resolveMobileRouteRedirect('/canvas')).toBe('/m/canvas')
    expect(resolveMobileRouteRedirect('/voice-notes')).toBe('/m/voice-notes')
    expect(resolveMobileRouteRedirect('/')).toBe('/m')
  })

  it('falls back to mobile hub for unmapped desktop paths', () => {
    expect(resolveMobileRouteRedirect('/library')).toBe('/m')
    expect(resolveMobileRouteRedirect('/showcase')).toBe('/m')
    expect(resolveMobileRouteRedirect('/training/builder')).toBe('/m')
  })

  it('sends training leads to the phone remote and teachers to the hub', () => {
    expect(resolveMobileRouteRedirect('/training', { isTrainingLead: true })).toBe('/m/training')
    expect(resolveMobileRouteRedirect('/training', { isTrainingLead: false })).toBe('/m')
    expect(resolveMobileRouteRedirect('/training')).toBe('/m')
  })

  it('recognizes mobile route paths', () => {
    expect(isMobileRoutePath('/m')).toBe(true)
    expect(isMobileRoutePath('/m/canvas')).toBe(true)
    expect(isMobileRoutePath('/canvas')).toBe(false)
  })

  it('skips redirect for auth, admin, and existing mobile routes', () => {
    expect(shouldSkipMobileRouteRedirect('/m/mindmate')).toBe(true)
    expect(shouldSkipMobileRouteRedirect('/auth')).toBe(true)
    expect(shouldSkipMobileRouteRedirect('/admin')).toBe(true)
    expect(shouldSkipMobileRouteRedirect('/dashboard/login')).toBe(true)
    expect(shouldSkipMobileRouteRedirect('/mindmate')).toBe(false)
  })

  it('moves a locked shell onto the matching route', () => {
    expect(pathForLockedClientShell('/mindmate', 'mobile')).toBe('/m/mindmate')
    expect(pathForLockedClientShell('/m/mindmate', 'mobile')).toBeNull()
    expect(pathForLockedClientShell('/m/canvas', 'desktop')).toBe('/canvas')
    expect(pathForLockedClientShell('/canvas', 'desktop')).toBeNull()
    expect(pathForLockedClientShell('/admin', 'mobile')).toBeNull()
    expect(pathForLockedClientShell('/m/account', 'desktop')).toBe('/mindmate')
    expect(pathForLockedClientShell('/training', 'mobile')).toBe('/m')
    expect(pathForLockedClientShell('/training', 'mobile', { isTrainingLead: true })).toBe(
      '/m/training'
    )
    expect(pathForLockedClientShell('/admin', 'desktop')).toBeNull()
  })

  it('settles after one redirect for the same shell', () => {
    const paths = ['/m', '/m/canvas', '/m/account', '/mindmate', '/canvas', '/training', '/admin']
    const shells = ['mobile', 'desktop'] as const
    for (const path of paths) {
      for (const shell of shells) {
        const next = pathForLockedClientShell(path, shell)
        if (!next) continue
        expect(pathForLockedClientShell(next, shell)).toBeNull()
      }
    }
  })
})
