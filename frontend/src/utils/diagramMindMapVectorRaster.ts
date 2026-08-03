/**
 * Rasterize vector mind-map SVG at print DPI for DOCX embedding.
 * Mounts SVG in the DOM so browser webfonts (Noto / Inter) apply before capture.
 */
import { loadHtmlToImageModule } from '@/utils/diagramExportHtmlToImage'

/** ~300 DPI relative to 96 CSS px. */
export const MIND_MAP_VECTOR_DOCX_PIXEL_RATIO = 3.125

export async function rasterizeMindMapVectorSvg(
  svg: string,
  options?: { pixelRatio?: number }
): Promise<{ blob: Blob; width: number; height: number }> {
  const pixelRatio = options?.pixelRatio ?? MIND_MAP_VECTOR_DOCX_PIXEL_RATIO
  const { toBlob } = await loadHtmlToImageModule()

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
    const blob = await toBlob(svgEl as unknown as HTMLElement, {
      backgroundColor: '#ffffff',
      pixelRatio,
      cacheBust: true,
    })
    if (!blob) {
      throw new Error('Vector SVG rasterize produced empty PNG')
    }
    const widthAttr = Number(svgEl.getAttribute('width')) || svgEl.clientWidth || 1
    const heightAttr = Number(svgEl.getAttribute('height')) || svgEl.clientHeight || 1
    return {
      blob,
      width: Math.max(1, Math.round(widthAttr * pixelRatio)),
      height: Math.max(1, Math.round(heightAttr * pixelRatio)),
    }
  } finally {
    host.remove()
  }
}
