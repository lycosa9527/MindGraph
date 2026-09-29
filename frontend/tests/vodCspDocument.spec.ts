import { describe, expect, it } from 'vitest'

import { shouldReloadForVodCsp } from '@/utils/vodCspDocument'

describe('shouldReloadForVodCsp', () => {
  it('reloads once in production when the library is on and the shell has no marker', () => {
    expect(shouldReloadForVodCsp(true, false, false, false)).toBe(true)
  })

  it('stays on the page when the shell already allows the player', () => {
    expect(shouldReloadForVodCsp(true, true, false, false)).toBe(false)
  })

  it('does not reload again after one attempt', () => {
    expect(shouldReloadForVodCsp(true, false, true, false)).toBe(false)
  })

  it('skips the reload in dev and when the library is off', () => {
    expect(shouldReloadForVodCsp(true, false, false, true)).toBe(false)
    expect(shouldReloadForVodCsp(false, false, false, false)).toBe(false)
  })
})
