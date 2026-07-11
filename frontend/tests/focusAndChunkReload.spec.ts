import { afterEach, describe, expect, it, vi } from 'vitest'

import { focusHtmlControl, selectHtmlControl } from '@/utils/focusHtmlControl'
import { isStaleChunkLoadError, reloadForStaleChunk } from '@/utils/staleChunkReload'

describe('focusHtmlControl', () => {
  it('focuses a real element', () => {
    const focus = vi.fn()
    expect(focusHtmlControl({ focus })).toBe(true)
    expect(focus).toHaveBeenCalledTimes(1)
  })

  it('returns false when focus is missing', () => {
    expect(focusHtmlControl({})).toBe(false)
    expect(focusHtmlControl(null)).toBe(false)
  })

  it('uses the first element from an array ref', () => {
    const focus = vi.fn()
    expect(focusHtmlControl([{ focus }])).toBe(true)
    expect(focus).toHaveBeenCalledTimes(1)
  })

  it('selects when select is a function', () => {
    const select = vi.fn()
    expect(selectHtmlControl({ select })).toBe(true)
    expect(select).toHaveBeenCalledTimes(1)
  })
})

describe('staleChunkReload', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    sessionStorage.clear()
  })

  it('detects dynamic import failures', () => {
    expect(
      isStaleChunkLoadError(new Error('Failed to fetch dynamically imported module: https://x/a.js'))
    ).toBe(true)
    expect(isStaleChunkLoadError(new Error('Unable to preload CSS for /assets/x.css'))).toBe(true)
    expect(isStaleChunkLoadError(new Error('boom'))).toBe(false)
  })

  it('reloads once within the cooldown window', () => {
    const reload = vi.fn()
    vi.stubGlobal('location', { reload })
    expect(reloadForStaleChunk(new Error('Failed to fetch dynamically imported module'))).toBe(true)
    expect(reload).toHaveBeenCalledTimes(1)
    expect(reloadForStaleChunk(new Error('Failed to fetch dynamically imported module'))).toBe(false)
    expect(reload).toHaveBeenCalledTimes(1)
  })
})
