/**
 * A4 PDF helpers for diagram raster export.
 */
import type { CanvasExportLayout } from '@/config/canvasExportOptions'

export type PdfPageOrientation = 'landscape' | 'portrait'

/** Print-oriented raster density — avoids embedding multi‑MB full-viewport PNGs. */
export const PDF_RASTER_DPI = 150
const MM_PER_INCH = 25.4
const A4_LANDSCAPE_MM = { width: 297, height: 210 }
const A4_PORTRAIT_MM = { width: 210, height: 297 }

export function resolvePdfOrientationFromSize(width: number, height: number): PdfPageOrientation {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return 'portrait'
  }
  return width > height ? 'landscape' : 'portrait'
}

export function resolvePdfOrientationFromCommand(
  command: string,
  imageWidth: number,
  imageHeight: number
): PdfPageOrientation {
  if (command === 'pdf_landscape') return 'landscape'
  if (command === 'pdf_portrait') return 'portrait'
  if (command === 'pdf') return resolvePdfOrientationFromSize(imageWidth, imageHeight)
  return resolvePdfOrientationFromSize(imageWidth, imageHeight)
}

export function resolvePdfOrientationFromExportOptions(
  command: string,
  imageWidth: number,
  imageHeight: number,
  layout?: CanvasExportLayout
): PdfPageOrientation {
  if (layout === 'landscape' || layout === 'portrait') {
    return layout
  }
  return resolvePdfOrientationFromCommand(command, imageWidth, imageHeight)
}

export function isPdfExportCommand(command: string): boolean {
  return command === 'pdf' || command === 'pdf_landscape' || command === 'pdf_portrait'
}

export function a4DrawablePixelBounds(
  orientation: PdfPageOrientation,
  dpi = PDF_RASTER_DPI,
  marginMm = 10
): { maxWidth: number; maxHeight: number } {
  const page = orientation === 'landscape' ? A4_LANDSCAPE_MM : A4_PORTRAIT_MM
  return {
    maxWidth: Math.round(((page.width - marginMm * 2) / MM_PER_INCH) * dpi),
    maxHeight: Math.round(((page.height - marginMm * 2) / MM_PER_INCH) * dpi),
  }
}

export function computePdfRasterTargetSize(
  sourceWidth: number,
  sourceHeight: number,
  orientation: PdfPageOrientation,
  dpi = PDF_RASTER_DPI,
  marginMm = 10
): { width: number; height: number } {
  const { maxWidth, maxHeight } = a4DrawablePixelBounds(orientation, dpi, marginMm)
  const scale = Math.min(1, maxWidth / sourceWidth, maxHeight / sourceHeight)
  return {
    width: Math.max(1, Math.round(sourceWidth * scale)),
    height: Math.max(1, Math.round(sourceHeight * scale)),
  }
}

export function pdfRasterFormatFromDataUrl(dataUrl: string): 'JPEG' | 'PNG' {
  return dataUrl.startsWith('data:image/jpeg') ? 'JPEG' : 'PNG'
}

export async function loadImageElement(dataUrl: string): Promise<HTMLImageElement> {
  const img = new Image()
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve()
    img.onerror = () => reject(new Error('Failed to decode export image'))
    img.src = dataUrl
  })
  return img
}

/** Downscale a canvas capture before embedding in jsPDF. */
export async function compressRasterDataUrlForA4Pdf(
  dataUrl: string,
  sourceWidth: number,
  sourceHeight: number,
  orientation: PdfPageOrientation,
  prefetchedImage?: HTMLImageElement
): Promise<{ dataUrl: string; width: number; height: number }> {
  const target = computePdfRasterTargetSize(sourceWidth, sourceHeight, orientation)
  const img = prefetchedImage ?? (await loadImageElement(dataUrl))

  const canvas = document.createElement('canvas')
  canvas.width = target.width
  canvas.height = target.height
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    throw new Error('Canvas 2D context unavailable for PDF compression')
  }

  ctx.drawImage(img, 0, 0, target.width, target.height)

  return {
    dataUrl: canvas.toDataURL('image/png'),
    width: target.width,
    height: target.height,
  }
}

type JsPdfLike = {
  internal: { pageSize: { getWidth: () => number; getHeight: () => number } }
  addImage: (
    imageData: string,
    format: string,
    x: number,
    y: number,
    width: number,
    height: number
  ) => void
  addPage: () => void
}

export function fitImageRectOnA4Page(
  pdf: JsPdfLike,
  imageWidthPx: number,
  imageHeightPx: number,
  marginMm = 10
): { x: number; y: number; width: number; height: number } {
  const pageW = pdf.internal.pageSize.getWidth()
  const pageH = pdf.internal.pageSize.getHeight()
  const maxW = pageW - marginMm * 2
  const maxH = pageH - marginMm * 2
  const aspect = imageWidthPx / imageHeightPx
  let drawW = maxW
  let drawH = drawW / aspect
  if (drawH > maxH) {
    drawH = maxH
    drawW = drawH * aspect
  }
  return {
    x: (pageW - drawW) / 2,
    y: (pageH - drawH) / 2,
    width: drawW,
    height: drawH,
  }
}

export function addRasterImageToA4PdfPage(
  pdf: JsPdfLike,
  dataUrl: string,
  imageWidthPx: number,
  imageHeightPx: number,
  marginMm = 10
): void {
  const rect = fitImageRectOnA4Page(pdf, imageWidthPx, imageHeightPx, marginMm)
  pdf.addImage(
    dataUrl,
    pdfRasterFormatFromDataUrl(dataUrl),
    rect.x,
    rect.y,
    rect.width,
    rect.height
  )
}

export function fitImageRectInA4Region(
  pdf: JsPdfLike,
  imageWidthPx: number,
  imageHeightPx: number,
  regionTopMm: number,
  marginMm = 10
): { x: number; y: number; width: number; height: number } {
  const pageW = pdf.internal.pageSize.getWidth()
  const pageH = pdf.internal.pageSize.getHeight()
  const maxW = pageW - marginMm * 2
  const maxH = pageH - regionTopMm - marginMm
  const aspect = imageWidthPx / imageHeightPx
  let drawW = maxW
  let drawH = drawW / aspect
  if (drawH > maxH) {
    drawH = maxH
    drawW = drawH * aspect
  }
  return {
    x: (pageW - drawW) / 2,
    y: regionTopMm + (maxH - drawH) / 2,
    width: drawW,
    height: drawH,
  }
}

export function addWorksheetPageToPdf(
  pdf: JsPdfLike,
  diagramDataUrl: string,
  diagramWidthPx: number,
  diagramHeightPx: number,
  headerDataUrl: string | null,
  headerWidthPx: number,
  headerHeightPx: number,
  marginMm = 10,
  headerGapMm = 4
): void {
  const pageW = pdf.internal.pageSize.getWidth()
  let regionTopMm = marginMm

  if (headerDataUrl && headerWidthPx > 0 && headerHeightPx > 0) {
    const headerMaxW = pageW - marginMm * 2
    const headerAspect = headerWidthPx / headerHeightPx
    const headerDrawW = headerMaxW
    const headerDrawH = headerDrawW / headerAspect
    pdf.addImage(
      headerDataUrl,
      pdfRasterFormatFromDataUrl(headerDataUrl),
      marginMm,
      regionTopMm,
      headerDrawW,
      headerDrawH
    )
    regionTopMm += headerDrawH + headerGapMm
  }

  const diagramRect = fitImageRectInA4Region(
    pdf,
    diagramWidthPx,
    diagramHeightPx,
    regionTopMm,
    marginMm
  )
  pdf.addImage(
    diagramDataUrl,
    pdfRasterFormatFromDataUrl(diagramDataUrl),
    diagramRect.x,
    diagramRect.y,
    diagramRect.width,
    diagramRect.height
  )
}
