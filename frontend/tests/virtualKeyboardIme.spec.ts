import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getNavigatorVirtualKeyboard,
  prepareFieldForSystemIme,
  showSystemVirtualKeyboard,
} from '@/utils/virtualKeyboardIme'

describe('virtual keyboard system IME', () => {
  afterEach(() => {
    document.body.replaceChildren()
    vi.unstubAllGlobals()
  })

  it('prepares the focused field for the system IME', () => {
    const input = document.createElement('input')
    document.body.appendChild(input)
    prepareFieldForSystemIme(input, 'zh')
    expect(input.lang).toBe('zh')
    expect(input.getAttribute('inputmode')).toBe('text')
    expect(document.activeElement).toBe(input)
  })

  it('shows the platform keyboard when the VirtualKeyboard API exists', () => {
    const show = vi.fn()
    vi.stubGlobal('navigator', {
      virtualKeyboard: { overlaysContent: false, show, hide: vi.fn() },
    })
    const input = document.createElement('input')
    document.body.appendChild(input)
    expect(getNavigatorVirtualKeyboard()).not.toBeNull()
    expect(showSystemVirtualKeyboard(input, 'en')).toBe(true)
    expect(show).toHaveBeenCalledTimes(1)
  })

  it('returns false when the platform keyboard API is missing', () => {
    vi.stubGlobal('navigator', {})
    const input = document.createElement('input')
    document.body.appendChild(input)
    expect(showSystemVirtualKeyboard(input, 'en')).toBe(false)
    expect(document.activeElement).toBe(input)
  })
})
