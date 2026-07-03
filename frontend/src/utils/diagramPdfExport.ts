/**
 * A4 PDF helpers for diagram raster export.
 */
export type PdfPageOrientation = 'landscape' | 'portrait'

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

export function isPdfExportCommand(command: string): boolean {
  return command === 'pdf' || command === 'pdf_landscape' || command === 'pdf_portrait'
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
  pdf.addImage(dataUrl, 'PNG', rect.x, rect.y, rect.width, rect.height)
}
