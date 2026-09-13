import { describe, expect, it } from 'vitest'

import {
  consumeSlideRemotePendingStart,
  peekSlideRemotePendingStart,
  setSlideRemotePendingStart,
  shouldJumpForSlideRemoteStart,
} from '@/utils/slideRemotePendingStart'

describe('slideRemotePendingStart', () => {
  it('jumps only when the library id is not already open', () => {
    expect(shouldJumpForSlideRemoteStart('diag-1', 'diag-1')).toBe(false)
    expect(shouldJumpForSlideRemoteStart('diag-1', 'diag-2')).toBe(true)
    expect(shouldJumpForSlideRemoteStart(null, 'diag-2')).toBe(true)
    expect(shouldJumpForSlideRemoteStart('diag-1', '')).toBe(false)
  })

  it('stores and consumes a matching start id', () => {
    sessionStorage.clear()
    setSlideRemotePendingStart(' diag-9 ')
    expect(peekSlideRemotePendingStart()).toBe('diag-9')
    expect(consumeSlideRemotePendingStart('diag-8')).toBe(false)
    expect(consumeSlideRemotePendingStart('diag-9')).toBe(true)
    expect(peekSlideRemotePendingStart()).toBeNull()
  })
})
