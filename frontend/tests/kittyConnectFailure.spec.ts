import { describe, expect, it } from 'vitest'

import {
  KITTY_WS_CLOSE_ACCESS,
  KITTY_WS_CLOSE_AUTH,
  KITTY_WS_CLOSE_BAD_SCOPE,
  KITTY_WS_CLOSE_GOING_AWAY,
  KITTY_WS_CLOSE_SCOPE_DENIED,
  classifyKittyWsCloseCode,
  isKittyWsIntentionalClose,
  isKittyWsPolicyDenyClose,
} from '@/composables/kitty/kittyConnectFailure'

describe('kittyConnectFailure helpers', () => {
  it('classifies Kitty policy close codes', () => {
    expect(classifyKittyWsCloseCode(KITTY_WS_CLOSE_AUTH)).toBe('auth_failed')
    expect(classifyKittyWsCloseCode(KITTY_WS_CLOSE_ACCESS)).toBe('access_denied')
    expect(classifyKittyWsCloseCode(KITTY_WS_CLOSE_BAD_SCOPE)).toBe('scope_denied')
    expect(classifyKittyWsCloseCode(KITTY_WS_CLOSE_SCOPE_DENIED)).toBe('scope_denied')
    expect(classifyKittyWsCloseCode(1006)).toBeNull()
  })

  it('detects intentional vs policy-deny closes', () => {
    expect(isKittyWsIntentionalClose(KITTY_WS_CLOSE_GOING_AWAY, false)).toBe(true)
    expect(isKittyWsIntentionalClose(1006, true)).toBe(true)
    expect(isKittyWsIntentionalClose(1006, false)).toBe(false)
    expect(isKittyWsPolicyDenyClose(KITTY_WS_CLOSE_ACCESS)).toBe(true)
    expect(isKittyWsPolicyDenyClose(KITTY_WS_CLOSE_SCOPE_DENIED)).toBe(true)
    expect(isKittyWsPolicyDenyClose(KITTY_WS_CLOSE_AUTH)).toBe(false)
  })
})
