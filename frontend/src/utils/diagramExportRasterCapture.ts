import { cropExportedDiagramCanvas } from '@/utils/diagramExportContentBounds'
import { loadHtmlToImageModule } from '@/utils/diagramExportHtmlToImage'
import { scaleExportSvgDataUrl } from '@/utils/diagramExportRasterScale'
import type { HtmlToImageOptions } from '@/utils/diagramHtmlToImage'
import { loadImageElement } from '@/utils/diagramPdfExport'

export type DiagramRasterCapture = {
  dataUrl: string
  width: number
  height: number
  image: HTMLImageElement
}

export async function rasterizeExportSvgDataUrl(
  svgDataUrl: string,
  requestedPixelRatio: number,
  backgroundColor?: string
): Promise<HTMLCanvasElement> {
  const scaled = scaleExportSvgDataUrl(svgDataUrl, requestedPixelRatio)
  const image = await loadImageElement(scaled.dataUrl)
  const canvas = document.createElement('canvas')
  canvas.width = scaled.width
  canvas.height = scaled.height
  const context = canvas.getContext('2d')
  if (!context) {
    throw new Error('Canvas 2D context unavailable for export')
  }
  if (backgroundColor) {
    context.fillStyle = backgroundColor
    context.fillRect(0, 0, canvas.width, canvas.height)
  }
  context.imageSmoothingEnabled = true
  context.imageSmoothingQuality = 'high'
  context.drawImage(image, 0, 0, scaled.width, scaled.height)
  return canvas
}

export async function captureDiagramRasterCanvas(
  container: HTMLElement,
  options: HtmlToImageOptions
): Promise<HTMLCanvasElement> {
  const { toSvg } = await loadHtmlToImageModule()
  const svgDataUrl = await toSvg(container, options)
  const canvas = await rasterizeExportSvgDataUrl(
    svgDataUrl,
    options.pixelRatio ?? 2,
    options.backgroundColor
  )
  return cropExportedDiagramCanvas(container, canvas)
}

export async function canvasToPngBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob)
        return
      }
      reject(new Error('PNG export produced empty image'))
    }, 'image/png')
  })
}

export async function captureDiagramPngBlob(
  container: HTMLElement,
  options: HtmlToImageOptions
): Promise<Blob> {
  const canvas = await captureDiagramRasterCanvas(container, options)
  return canvasToPngBlob(canvas)
}

export async function captureDiagramPngData(
  container: HTMLElement,
  options: HtmlToImageOptions
): Promise<DiagramRasterCapture> {
  const canvas = await captureDiagramRasterCanvas(container, options)
  const dataUrl = canvas.toDataURL('image/png')
  const image = await loadImageElement(dataUrl)
  return {
    dataUrl,
    width: canvas.width,
    height: canvas.height,
    image,
  }
}
