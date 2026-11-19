/**
 * Worksheet compare layout geometry (A4 content region).
 * horizontal = left | right; vertical = top / bottom.
 */

export type WorksheetCompareArrangement = 'horizontal' | 'vertical'

export type WorksheetComparePanelRect = {
  x: number
  y: number
  width: number
  height: number
}

export type WorksheetCompareLayout = {
  first: WorksheetComparePanelRect
  second: WorksheetComparePanelRect
  /** @deprecated alias of first — kept for call sites that still say left/right */
  left: WorksheetComparePanelRect
  /** @deprecated alias of second */
  right: WorksheetComparePanelRect
  gapMm: number
  labelHeightMm: number
  arrangement: WorksheetCompareArrangement
}

const DEFAULT_GAP_MM = 6
const DEFAULT_LABEL_HEIGHT_MM = 6

export function normalizeWorksheetCompareArrangement(value: unknown): WorksheetCompareArrangement {
  return value === 'vertical' ? 'vertical' : 'horizontal'
}

/**
 * Split a content region into two equal panels with a centre gap.
 * Label strip is reserved under (horizontal) or beside (not used) each panel —
 * callers draw captions in the reserved strip below each panel.
 */
export function splitWorksheetCompareRegion(
  regionX: number,
  regionY: number,
  regionWidth: number,
  regionHeight: number,
  gapMm = DEFAULT_GAP_MM,
  labelHeightMm = DEFAULT_LABEL_HEIGHT_MM,
  arrangement: WorksheetCompareArrangement = 'horizontal'
): WorksheetCompareLayout {
  const gap = Math.max(0, gapMm)
  const labelH = Math.max(0, labelHeightMm)
  const mode = normalizeWorksheetCompareArrangement(arrangement)

  if (mode === 'vertical') {
    const panelW = Math.max(1, regionWidth)
    const panelH = Math.max(1, (regionHeight - gap - labelH * 2) / 2)
    const first: WorksheetComparePanelRect = {
      x: regionX,
      y: regionY,
      width: panelW,
      height: panelH,
    }
    const second: WorksheetComparePanelRect = {
      x: regionX,
      y: regionY + panelH + labelH + gap,
      width: panelW,
      height: panelH,
    }
    return {
      arrangement: mode,
      gapMm: gap,
      labelHeightMm: labelH,
      first,
      second,
      left: first,
      right: second,
    }
  }

  const panelW = Math.max(1, (regionWidth - gap) / 2)
  const panelH = Math.max(1, regionHeight - labelH)
  const first: WorksheetComparePanelRect = {
    x: regionX,
    y: regionY,
    width: panelW,
    height: panelH,
  }
  const second: WorksheetComparePanelRect = {
    x: regionX + panelW + gap,
    y: regionY,
    width: panelW,
    height: panelH,
  }
  return {
    arrangement: mode,
    gapMm: gap,
    labelHeightMm: labelH,
    first,
    second,
    left: first,
    right: second,
  }
}

/** Fit an image into a panel while preserving aspect ratio (centred). */
export function fitImageInPanel(
  imageWidthPx: number,
  imageHeightPx: number,
  panel: WorksheetComparePanelRect
): WorksheetComparePanelRect {
  const aspect = imageWidthPx > 0 && imageHeightPx > 0 ? imageWidthPx / imageHeightPx : 1
  let width = panel.width
  let height = width / aspect
  if (height > panel.height) {
    height = panel.height
    width = height * aspect
  }
  return {
    x: panel.x + (panel.width - width) / 2,
    y: panel.y + (panel.height - height) / 2,
    width,
    height,
  }
}

function clampOffset(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.max(-1, Math.min(1, value))
}

function clampScale(value: number): number {
  if (!Number.isFinite(value)) return 1
  return Math.max(0.25, Math.min(1, value))
}

/**
 * Max-fit then apply worksheet placement (offset [-1,1], scale 0.25–1)
 * inside a compare panel — same math as single-diagram free space.
 */
export function placeImageInComparePanel(
  imageWidthPx: number,
  imageHeightPx: number,
  panel: WorksheetComparePanelRect,
  offsetX = 0,
  offsetY = 0,
  scale = 1
): WorksheetComparePanelRect {
  const fitted = fitImageInPanel(imageWidthPx, imageHeightPx, panel)
  const s = clampScale(scale)
  const width = fitted.width * s
  const height = fitted.height * s
  const freeW = Math.max(0, panel.width - width)
  const freeH = Math.max(0, panel.height - height)
  const ox = clampOffset(offsetX)
  const oy = clampOffset(offsetY)
  return {
    x: panel.x + freeW / 2 + (ox * freeW) / 2,
    y: panel.y + freeH / 2 + (oy * freeH) / 2,
    width,
    height,
  }
}
