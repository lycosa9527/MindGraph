import { FIT_PADDING } from '@/config/uiConfig'

/** Left fit-view reserve when the mind map v2 side toolbar is on screen. */
export function resolveMindMapSideToolbarLeftReservePx(input: {
  active: boolean
  expanded: boolean
}): number {
  if (!input.active) {
    return FIT_PADDING.STANDARD_PX
  }

  const geometry = FIT_PADDING.MIND_MAP_SIDE_TOOLBAR
  const occupied =
    geometry.OFFSET_LEFT_PX +
    geometry.HANDLE_WIDTH_PX +
    (input.expanded ? geometry.CARD_WIDTH_PX : 0) +
    geometry.BUFFER_PX

  return Math.max(FIT_PADDING.STANDARD_PX, occupied)
}

export function parseFitPaddingPx(value: string | number): number {
  if (typeof value === 'number') return value
  const parsed = Number.parseFloat(value)
  return Number.isFinite(parsed) ? parsed : FIT_PADDING.STANDARD_PX
}
