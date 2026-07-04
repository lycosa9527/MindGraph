import { loadHtmlToImageModule } from '@/utils/diagramExportHtmlToImage'
import { cropExportedDiagramCanvas } from '@/utils/diagramExportContentBounds'
import type { HtmlToImageOptions } from '@/utils/diagramHtmlToImage'
import { loadImageElement } from '@/utils/diagramPdfExport'

export type DiagramRasterCapture = {
  dataUrl: string
  width: number
  height: number
  image: HTMLImageElement
}

export async function captureDiagramRasterCanvas(
  container: HTMLElement,
  options: HtmlToImageOptions
): Promise<HTMLCanvasElement> {
  const { toCanvas } = await loadHtmlToImageModule()
  const canvas = await toCanvas(container, options)
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
