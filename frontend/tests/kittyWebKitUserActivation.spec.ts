/**
 * WebKit / HTML activation-triggering event helpers for Kitty PTT.
 */
import { describe, expect, it } from 'vitest'

import {
  isActivationTriggeringEvent,
  pointerDownGrantsActivation,
  pointerUpGrantsActivation,
} from '@/composables/kitty/kittyWebKitUserActivation'

describe('kittyWebKitUserActivation', () => {
  it('matches WebKit activation-triggering pointer rules', () => {
    const mouseDown = new PointerEvent('pointerdown', { pointerType: 'mouse' })
    const touchDown = new PointerEvent('pointerdown', { pointerType: 'touch' })
    const mouseUp = new PointerEvent('pointerup', { pointerType: 'mouse' })
    const touchUp = new PointerEvent('pointerup', { pointerType: 'touch' })
    const penUp = new PointerEvent('pointerup', { pointerType: 'pen' })

    expect(pointerDownGrantsActivation(mouseDown)).toBe(true)
    expect(pointerDownGrantsActivation(touchDown)).toBe(false)
    expect(pointerUpGrantsActivation(mouseUp)).toBe(false)
    expect(pointerUpGrantsActivation(touchUp)).toBe(true)
    expect(pointerUpGrantsActivation(penUp)).toBe(true)

    expect(isActivationTriggeringEvent(mouseDown)).toBe(true)
    expect(isActivationTriggeringEvent(touchDown)).toBe(false)
    expect(isActivationTriggeringEvent(mouseUp)).toBe(false)
    expect(isActivationTriggeringEvent(touchUp)).toBe(true)
    expect(isActivationTriggeringEvent(new KeyboardEvent('keydown', { key: 'a' }))).toBe(true)
    expect(isActivationTriggeringEvent(new KeyboardEvent('keydown', { key: 'Escape' }))).toBe(
      false
    )
    expect(isActivationTriggeringEvent(new Event('touchend'))).toBe(true)
    expect(isActivationTriggeringEvent(new Event('mousedown'))).toBe(true)
    expect(isActivationTriggeringEvent(new Event('click'))).toBe(true)
  })
})
