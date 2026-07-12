/**
 * Desktop one-sentence yields edit input to Mobile Kitty on the same scope.
 */
import { describe, expect, it } from 'vitest'

import { shouldLockDesktopOneSentenceForMobileKitty } from '@/composables/canvasToolbar/desktopOneSentenceMobileKittyLock'

describe('shouldLockDesktopOneSentenceForMobileKitty', () => {
  const mobileOnScope = {
    active: true,
    scopes: ['lib-diagram-1'],
    primaryScope: 'lib-diagram-1',
  }

  it('locks edit when mobile is active on the same diagram scope', () => {
    expect(
      shouldLockDesktopOneSentenceForMobileKitty({
        phase: 'edit',
        diagramScope: 'lib-diagram-1',
        mobile: mobileOnScope,
      })
    ).toBe(true)
  })

  it('does not lock create phase (desktop owns generate)', () => {
    expect(
      shouldLockDesktopOneSentenceForMobileKitty({
        phase: 'create',
        diagramScope: 'lib-diagram-1',
        mobile: mobileOnScope,
      })
    ).toBe(false)
  })

  it('does not lock when mobile is inactive', () => {
    expect(
      shouldLockDesktopOneSentenceForMobileKitty({
        phase: 'edit',
        diagramScope: 'lib-diagram-1',
        mobile: { active: false, scopes: ['lib-diagram-1'], primaryScope: 'lib-diagram-1' },
      })
    ).toBe(false)
  })

  it('does not lock when mobile is on a different scope', () => {
    expect(
      shouldLockDesktopOneSentenceForMobileKitty({
        phase: 'edit',
        diagramScope: 'lib-diagram-1',
        mobile: { active: true, scopes: ['other-scope'], primaryScope: 'other-scope' },
      })
    ).toBe(false)
  })

  it('does not lock without a diagram scope', () => {
    expect(
      shouldLockDesktopOneSentenceForMobileKitty({
        phase: 'edit',
        diagramScope: '',
        mobile: mobileOnScope,
      })
    ).toBe(false)
  })
})
