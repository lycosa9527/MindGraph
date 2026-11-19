/**
 * Pure camera math for a MindGlass nudge. The open editor applies the result.
 */
import { ZOOM } from '@/config/uiConfig'

export type GlassesViewport = { x: number; y: number; zoom: number }

const PAN_PX = 140

function clampZoom(zoom: number): number {
  return Math.min(ZOOM.MAX, Math.max(ZOOM.MIN, zoom))
}

/** Next camera, a fit request, or null when the action is not a remote nudge. */
export function nextGlassesViewport(
  viewport: GlassesViewport,
  action: string
): GlassesViewport | 'fit' | null {
  switch (action) {
    case 'pan_left':
      return { ...viewport, x: viewport.x + PAN_PX }
    case 'pan_right':
      return { ...viewport, x: viewport.x - PAN_PX }
    case 'pan_up':
      return { ...viewport, y: viewport.y + PAN_PX }
    case 'pan_down':
      return { ...viewport, y: viewport.y - PAN_PX }
    case 'zoom_in':
      return { ...viewport, zoom: clampZoom(viewport.zoom * ZOOM.STEP) }
    case 'zoom_out':
      return { ...viewport, zoom: clampZoom(viewport.zoom / ZOOM.STEP) }
    case 'fit':
      return 'fit'
    default:
      return null
  }
}
