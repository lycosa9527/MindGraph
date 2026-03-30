/**
 * Shared html-to-image settings for diagram canvas export (PNG/SVG/PDF thumbnails).
 * Keeps rasterization consistent and excludes UI chrome that should not appear in files.
 */
import { toBlob } from 'html-to-image'

type HtmlToImageOptions = NonNullable<Parameters<typeof toBlob>[1]>

/** Wait until after the next two animation frames (layout + paint after Vue/DOM updates). */
export function waitForNextPaint(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve())
    })
  })
}

function isInsideVueFlowMinimap(node: Node): boolean {
  return node instanceof HTMLElement && Boolean(node.closest('.vue-flow__minimap'))
}

export function getDiagramCanvasHtmlToImageOptions(
  overrides?: Partial<HtmlToImageOptions>
): HtmlToImageOptions {
  return {
    backgroundColor: '#ffffff',
    pixelRatio: 2,
    style: { transform: 'none' },
    filter: (node: Node) => !isInsideVueFlowMinimap(node),
    ...overrides,
  }
}
