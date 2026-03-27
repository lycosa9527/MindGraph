import { GRID, ZOOM } from '@/config/uiConfig'

export const diagramCanvasZoomConfig = {
  min: ZOOM.MIN,
  max: ZOOM.MAX,
  default: ZOOM.DEFAULT,
} as const

export const diagramCanvasGridConfig = {
  snapSize: [...GRID.SNAP_SIZE] as [number, number],
  backgroundGap: GRID.BACKGROUND_GAP,
  backgroundDotSize: GRID.BACKGROUND_DOT_SIZE,
} as const
