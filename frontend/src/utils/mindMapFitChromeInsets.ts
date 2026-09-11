import { FIT_PADDING } from '@/config/uiConfig'

export type DiagramFitChromeInsets = {
  top: number
  right: number
  bottom: number
  left: number
}

export type DiagramFitChromeInsetsInput = {
  /** New-canvas ribbon: title + tools + status bar sit in page flow, not over Vue Flow. */
  ribbonChrome: boolean
  conceptMap: boolean
  treeMapAltDims: boolean
  presentationRailVisible: boolean
}

export function formatFitPaddingPx(value: number): string {
  return `${value}px`
}

/**
 * Fit-view / keep-visible insets for the current canvas chrome.
 * Ribbon chrome is in the page flex layout, so only edge breathing room is reserved.
 * Classic canvas overlays the merged header and floating zoom/AI cluster.
 */
export function resolveDiagramFitChromeInsetsPx(
  input: DiagramFitChromeInsetsInput
): DiagramFitChromeInsets {
  const top = resolveFitTopPx(input)
  const bottom = resolveFitBottomPx(input)
  const right = input.presentationRailVisible
    ? Math.max(FIT_PADDING.STANDARD_PX, FIT_PADDING.PRESENTATION_SIDE_TOOLBAR_RIGHT_PX)
    : FIT_PADDING.STANDARD_PX

  return {
    top,
    right,
    bottom,
    left: FIT_PADDING.STANDARD_PX,
  }
}

function resolveFitTopPx(input: DiagramFitChromeInsetsInput): number {
  if (input.ribbonChrome) {
    return FIT_PADDING.STANDARD_PX
  }
  if (input.conceptMap) {
    return FIT_PADDING.TOP_UI_HEIGHT_PX + FIT_PADDING.MAIN_TOPIC_MENU_ICON_PX
  }
  return FIT_PADDING.TOP_UI_HEIGHT_PX
}

function resolveFitBottomPx(input: DiagramFitChromeInsetsInput): number {
  const base = input.ribbonChrome
    ? FIT_PADDING.STANDARD_PX
    : FIT_PADDING.BOTTOM_UI_HEIGHT_PX
  if (!input.treeMapAltDims) {
    return base
  }
  return base + FIT_PADDING.TREE_MAP_ALTERNATIVE_DIMENSIONS_EXTRA_PX
}
