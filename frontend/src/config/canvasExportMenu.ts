/**
 * Canvas export dropdown commands — shared between CanvasTopBar and mind-map toolbar.
 * Raster formats (png/svg/pdf) use fit-for-export + html-to-image; mg uses spec export.
 */
export type CanvasRasterExportCommand = 'png' | 'svg' | 'pdf_landscape' | 'pdf_portrait'

export type CanvasSpecExportCommand = 'mg'

export type CanvasCommunityExportCommand = 'community'

/** Legacy alias — resolves to landscape/portrait from diagram aspect ratio at export time. */
export type CanvasLegacyPdfExportCommand = 'pdf'

export type CanvasExportCommand =
  | CanvasRasterExportCommand
  | CanvasLegacyPdfExportCommand
  | CanvasSpecExportCommand
  | CanvasCommunityExportCommand

export type CanvasExportMenuItem = {
  command: CanvasRasterExportCommand | CanvasLegacyPdfExportCommand | CanvasSpecExportCommand
  labelKey: string
  divided?: boolean
}

export const CANVAS_STANDARD_EXPORT_MENU_ITEMS: readonly CanvasExportMenuItem[] = [
  { command: 'png', labelKey: 'canvas.topBar.exportPng' },
  { command: 'svg', labelKey: 'canvas.topBar.exportSvg' },
  { command: 'pdf_landscape', labelKey: 'canvas.topBar.exportPdfLandscape' },
  { command: 'pdf_portrait', labelKey: 'canvas.topBar.exportPdfPortrait' },
  { command: 'mg', labelKey: 'canvas.topBar.exportJson', divided: true },
]

export const CANVAS_RASTER_EXPORT_COMMANDS: readonly CanvasRasterExportCommand[] = [
  'png',
  'svg',
  'pdf_landscape',
  'pdf_portrait',
]

export const CANVAS_COMMUNITY_EXPORT_MENU_ITEM = {
  command: 'community' as CanvasCommunityExportCommand,
  labelKey: 'canvas.topBar.shareCommunity',
  divided: true,
}

/** Mind map v2 export menu — PDF orientation comes from export options panel. */
export const CANVAS_MINDMAP_EXPORT_MENU_ITEMS: readonly CanvasExportMenuItem[] = [
  { command: 'png', labelKey: 'canvas.topBar.exportPng' },
  { command: 'svg', labelKey: 'canvas.topBar.exportSvg' },
  { command: 'pdf', labelKey: 'canvas.topBar.exportPdf' },
  { command: 'mg', labelKey: 'canvas.topBar.exportJson', divided: true },
]
