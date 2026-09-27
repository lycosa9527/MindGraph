/**
 * Rasterize vector mind-map SVG at print DPI for DOCX embedding.
 * Mounts SVG in the DOM so browser webfonts (Noto / Inter) apply before capture.
 */
import { loadHtmlToImageModule } from '@/utils/diagramExportHtmlToImage'
import { canvasToPngBlob, rasterizeExportSvgDataUrl } from '@/utils/diagramExportRasterCapture'

/** ~300 DPI relative to 96 CSS px. */
export const MIND_MAP_VECTOR_DOCX_PIXEL_RATIO = 3.125

export async function rasterizeMindMapVectorSvg(
  svg: string,
  options?: { pixelRatio?: number }
): Promise<{ blob: Blob; width: number; height: number }> {
  const pixelRatio = options?.pixelRatio ?? MIND_MAP_VECTOR_DOCX_PIXEL_RATIO
  const { toSvg } = await loadHtmlToImageModule()

  const host = document.createElement('div')
  host.setAttribute('data-mindmap-vector-raster', '1')
  host.style.cssText =
    'position:fixed;left:-10000px;top:0;pointer-events:none;opacity:1;background:#fff;'
  host.innerHTML = svg.replace(/^<\?xml[^>]*>/, '')
  const svgEl = host.querySelector('svg')
  if (!svgEl) {
    throw new Error('Vector SVG rasterize failed: no <svg> root')
  }
  document.body.appendChild(host)

  try {
    if (typeof document !== 'undefined' && document.fonts?.ready) {
      await document.fonts.ready
    }
    const svgDataUrl = await toSvg(svgEl as unknown as HTMLElement, {
      backgroundColor: '#ffffff',
      cacheBust: true,
    })
    const canvas = await rasterizeExportSvgDataUrl(svgDataUrl, pixelRatio, '#ffffff')
    const blob = await canvasToPngBlob(canvas)
    return {
      blob,
      width: canvas.width,
      height: canvas.height,
    }
  } finally {
    host.remove()
  }
}
