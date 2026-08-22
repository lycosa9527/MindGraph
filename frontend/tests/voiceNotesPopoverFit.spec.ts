import { describe, expect, it } from 'vitest'

import { placePopoverNearTrigger } from '@/utils/voiceNotesPopoverFit'

const clip = { left: 8, top: 8, right: 400, bottom: 700 }

describe('placePopoverNearTrigger', () => {
  it('opens below the trigger when that side has room', () => {
    const placed = placePopoverNearTrigger(
      { left: 200, top: 40, right: 280, bottom: 72 },
      { width: 264, height: 160 },
      'below',
      clip
    )
    expect(placed.top).toBe(80)
    expect(placed.left + 264).toBeLessThanOrEqual(clip.right)
  })

  it('flips above when the preferred below side is tight', () => {
    const placed = placePopoverNearTrigger(
      { left: 40, top: 620, right: 160, bottom: 652 },
      { width: 264, height: 200 },
      'below',
      clip
    )
    expect(placed.top + 200).toBeLessThanOrEqual(652)
    expect(placed.top).toBeGreaterThanOrEqual(clip.top)
  })

  it('shifts a left-side dock panel back onto the screen', () => {
    const placed = placePopoverNearTrigger(
      { left: 12, top: 600, right: 132, bottom: 636 },
      { width: 264, height: 180 },
      'above',
      clip
    )
    expect(placed.left).toBe(clip.left)
    expect(placed.left + 264).toBeLessThanOrEqual(clip.right)
    expect(placed.top).toBeGreaterThanOrEqual(clip.top)
  })

  it('caps height when the popover is taller than the remaining viewport', () => {
    const placed = placePopoverNearTrigger(
      { left: 80, top: 40, right: 200, bottom: 72 },
      { width: 200, height: 2000 },
      'below',
      clip
    )
    expect(placed.maxHeight).toBeLessThan(clip.bottom - 72)
    expect(placed.maxHeight).toBeGreaterThan(90)
  })
})
