import { describe, expect, it } from 'vitest'

import { FIT_PADDING } from '@/config/uiConfig'
import { resolveMindMapSideToolbarLeftReservePx } from '@/utils/mindMapSideToolbarFitReserve'

describe('resolveMindMapSideToolbarLeftReservePx', () => {
  it('uses standard padding when the toolbar is not active', () => {
    expect(
      resolveMindMapSideToolbarLeftReservePx({ active: false, expanded: false })
    ).toBe(FIT_PADDING.STANDARD_PX)
    expect(
      resolveMindMapSideToolbarLeftReservePx({ active: false, expanded: true })
    ).toBe(FIT_PADDING.STANDARD_PX)
  })

  it('reserves collapsed handle strip width when expanded card is hidden', () => {
    const { OFFSET_LEFT_PX, HANDLE_WIDTH_PX, BUFFER_PX } = FIT_PADDING.MIND_MAP_SIDE_TOOLBAR
    expect(
      resolveMindMapSideToolbarLeftReservePx({ active: true, expanded: false })
    ).toBe(OFFSET_LEFT_PX + HANDLE_WIDTH_PX + BUFFER_PX)
  })

  it('reserves expanded card width when the toolbar is open', () => {
    const { OFFSET_LEFT_PX, HANDLE_WIDTH_PX, CARD_WIDTH_PX, BUFFER_PX } =
      FIT_PADDING.MIND_MAP_SIDE_TOOLBAR
    expect(
      resolveMindMapSideToolbarLeftReservePx({ active: true, expanded: true })
    ).toBe(OFFSET_LEFT_PX + HANDLE_WIDTH_PX + CARD_WIDTH_PX + BUFFER_PX)
  })
})
