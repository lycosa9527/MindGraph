/**
 * Zoom and pan for the enlarged image preview.
 * Scale 1 is the fitted picture. The wheel changes scale about a point in
 * stage coordinates whose origin is the center of the frame.
 */

export const IMAGE_PREVIEW_MIN_SCALE = 1
export const IMAGE_PREVIEW_MAX_SCALE = 6

export interface ImagePreviewTransform {
  scale: number
  x: number
  y: number
}

/** Map a wheel delta into pixels. Line and page modes are not already pixels. */
export function wheelPixels(deltaY: number, deltaMode: number): number {
  if (deltaMode === 1) return deltaY * 16
  if (deltaMode === 2) return deltaY * 400
  return deltaY
}

/** Next scale for one wheel event. Wheel up zooms in. */
export function nextPreviewScale(scale: number, deltaY: number, deltaMode: number): number {
  const pixels = wheelPixels(deltaY, deltaMode)
  if (pixels === 0) return scale
  const capped = Math.max(-120, Math.min(120, pixels))
  const next = scale * Math.exp(-capped * 0.004)
  return Math.min(IMAGE_PREVIEW_MAX_SCALE, Math.max(IMAGE_PREVIEW_MIN_SCALE, next))
}

/**
 * Zoom about a cursor point so that point stays under the cursor.
 * `cursorX` and `cursorY` are offsets from the stage center.
 */
export function zoomAboutPoint(
  transform: ImagePreviewTransform,
  nextScale: number,
  cursorX: number,
  cursorY: number
): ImagePreviewTransform {
  if (nextScale === transform.scale) return transform
  const ratio = nextScale / transform.scale
  return {
    scale: nextScale,
    x: cursorX - (cursorX - transform.x) * ratio,
    y: cursorY - (cursorY - transform.y) * ratio,
  }
}

function clampAxis(value: number, limit: number): number {
  if (limit <= 0) return 0
  return Math.min(limit, Math.max(-limit, value))
}

/** Keep the scaled picture from being dragged entirely out of the frame. */
export function clampPreviewPan(
  transform: ImagePreviewTransform,
  viewWidth: number,
  viewHeight: number,
  imageWidth: number,
  imageHeight: number
): ImagePreviewTransform {
  const overflowX = Math.max(0, (imageWidth * transform.scale - viewWidth) / 2)
  const overflowY = Math.max(0, (imageHeight * transform.scale - viewHeight) / 2)
  return {
    scale: transform.scale,
    x: clampAxis(transform.x, overflowX),
    y: clampAxis(transform.y, overflowY),
  }
}
