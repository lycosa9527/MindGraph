import { describe, expect, it } from 'vitest'

import {
  isMobileRoutePath,
  resolveMobileRouteRedirect,
  shouldSkipMobileRouteRedirect,
} from '@/utils/mobileRouteRedirect'

describe('mobileRouteRedirect', () => {
  it('maps desktop paths to mobile equivalents', () => {
    expect(resolveMobileRouteRedirect('/mindmate')).toBe('/m/mindmate')
    expect(resolveMobileRouteRedirect('/mindgraph')).toBe('/m/mindgraph')
    expect(resolveMobileRouteRedirect('/canvas')).toBe('/m/canvas')
    expect(resolveMobileRouteRedirect('/')).toBe('/m')
  })

  it('falls back to mobile hub for unmapped desktop paths', () => {
    expect(resolveMobileRouteRedirect('/library')).toBe('/m')
    expect(resolveMobileRouteRedirect('/showcase')).toBe('/m')
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
})
