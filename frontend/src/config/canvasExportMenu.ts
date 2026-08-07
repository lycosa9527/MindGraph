/**
 * Canvas export dropdown commands — shared between CanvasTopBar and mind-map toolbar.
 * Mind maps: SVG/PDF/DOCX diagram body from model→vector SVG (PNG menu stays html-to-image).
 * Other diagrams: png/svg/pdf use fit-for-export + html-to-image; mg uses spec export.
 */
export type CanvasRasterExportCommand = 'png' | 'svg' | 'pdf_landscape' | 'pdf_portrait'

export type CanvasSpecExportCommand = 'mg'

export type CanvasCommunityExportCommand = 'community'

export type CanvasZhihuiDiagramCommand = 'zhihui_diagram'

/** Legacy alias — resolves to landscape/portrait from diagram aspect ratio at export time. */
export type CanvasLegacyPdfExportCommand = 'pdf'

export type CanvasExportCommand =
  | CanvasRasterExportCommand
  | CanvasLegacyPdfExportCommand
  | CanvasSpecExportCommand
  | CanvasCommunityExportCommand
  | CanvasZhihuiDiagramCommand

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

/** Open 智绘 图示生图 — visible only with ``feature.zhihui`` (superadmin). */
export const CANVAS_ZHIHUI_DIAGRAM_MENU_ITEM = {
  command: 'zhihui_diagram' as CanvasZhihuiDiagramCommand,
  labelKey: 'zhihui.mode.diagram',
  divided: true,
} as const

/** Mind map v2 export menu — DOCX/PDF (with paper orientation) lives in the worksheet modal. */
export const CANVAS_MINDMAP_EXPORT_MENU_ITEMS: readonly CanvasExportMenuItem[] = [
  { command: 'png', labelKey: 'canvas.topBar.exportPng' },
  { command: 'svg', labelKey: 'canvas.topBar.exportSvg' },
  { command: 'mg', labelKey: 'canvas.topBar.exportJson', divided: true },
]

export const CANVAS_WORKSHEET_TEXT_MENU_ITEM = {
  labelKey: 'canvas.topBar.addWorksheetText',
  divided: true,
} as const
