/**
 * Canvas export dropdown commands — shared between CanvasTopBar and mind-map toolbar.
 * Raster formats (png/svg/pdf) use fit-for-export + html-to-image; mg uses spec export.
 */
export type CanvasRasterExportCommand = 'png' | 'svg' | 'pdf'

export type CanvasSpecExportCommand = 'mg'

export type CanvasCommunityExportCommand = 'community'

export type CanvasExportCommand =
  | CanvasRasterExportCommand
  | CanvasSpecExportCommand
  | CanvasCommunityExportCommand

export type CanvasExportMenuItem = {
  command: CanvasRasterExportCommand | CanvasSpecExportCommand
  labelKey: string
  divided?: boolean
}

export const CANVAS_STANDARD_EXPORT_MENU_ITEMS: readonly CanvasExportMenuItem[] = [
  { command: 'png', labelKey: 'canvas.topBar.exportPng' },
  { command: 'svg', labelKey: 'canvas.topBar.exportSvg' },
  { command: 'pdf', labelKey: 'canvas.topBar.exportPdf' },
  { command: 'mg', labelKey: 'canvas.topBar.exportJson', divided: true },
]

export const CANVAS_RASTER_EXPORT_COMMANDS: readonly CanvasRasterExportCommand[] = [
  'png',
  'svg',
  'pdf',
]

export const CANVAS_COMMUNITY_EXPORT_MENU_ITEM = {
  command: 'community' as CanvasCommunityExportCommand,
  labelKey: 'canvas.topBar.shareCommunity',
  divided: true,
}
