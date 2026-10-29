import { describe, expect, it } from 'vitest'

import { foldCanvasNeedsRefit } from '@/composables/diagramCanvas/useFoldableCanvasRefit'
import { isHarmonyOsPhoneUserAgent, readVisualViewportBox } from '@/utils/arkWebClient'

const PHONE_UA =
  'Mozilla/5.0 (Phone; OpenHarmony 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36  ArkWeb/4.1.6.1 Mobile'
const TABLET_UA =
  'Mozilla/5.0 (Tablet; OpenHarmony 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36  ArkWeb/4.1.6.1'
const PC_UA =
  'Mozilla/5.0 (PC; OpenHarmony 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36  ArkWeb/4.1.6.1'

describe('isHarmonyOsPhoneUserAgent', () => {
  it('follows the documented device type', () => {
    expect(isHarmonyOsPhoneUserAgent(PHONE_UA)).toBe(true)
    expect(isHarmonyOsPhoneUserAgent(`${PHONE_UA} HuaweiBrowser/5.0.0`)).toBe(true)
    expect(isHarmonyOsPhoneUserAgent(TABLET_UA)).toBe(false)
    expect(isHarmonyOsPhoneUserAgent(PC_UA)).toBe(false)
    expect(isHarmonyOsPhoneUserAgent(`${PC_UA} Mobile`)).toBe(false)
    expect(isHarmonyOsPhoneUserAgent('Mozilla/5.0 ArkWeb/4.1.6.1 Mobile')).toBe(false)
  })
})

describe('readVisualViewportBox', () => {
  it('ignores a zero box reported mid-fold and uses the window when there is no visual viewport', () => {
    expect(
      readVisualViewportBox(
        { width: 0, height: 0, offsetTop: 0, offsetLeft: 0 },
        { width: 360, height: 780 }
      )
    ).toBeNull()
    expect(readVisualViewportBox(null, { width: 360, height: 780 })).toEqual({
      width: 360,
      height: 780,
      offsetTop: 0,
      offsetLeft: 0,
    })
  })

  it('uses the visual viewport, including the browser-chrome offset', () => {
    expect(
      readVisualViewportBox(
        { width: 346, height: 700, offsetTop: 48, offsetLeft: 0 },
        { width: 346, height: 780 }
      )
    ).toEqual({ width: 346, height: 700, offsetTop: 48, offsetLeft: 0 })
  })
})

describe('foldCanvasNeedsRefit', () => {
  it('refits a touch client when the fold changes the width', () => {
    expect(foldCanvasNeedsRefit(1220, 1120, 346, 781, true)).toBe(true)
    expect(foldCanvasNeedsRefit(440, 707, 327, 327, true)).toBe(true)
  })

  it('ignores a keyboard shrink and a desktop window drag', () => {
    expect(foldCanvasNeedsRefit(390, 780, 390, 420, true)).toBe(false)
    expect(foldCanvasNeedsRefit(1280, 800, 1100, 800, false)).toBe(false)
  })

  it('refits once a zero canvas box recovers', () => {
    expect(foldCanvasNeedsRefit(0, 0, 390, 640, false)).toBe(true)
  })
})
