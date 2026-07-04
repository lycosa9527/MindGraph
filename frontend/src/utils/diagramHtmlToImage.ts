/**
 * Shared html-to-image settings for diagram canvas export (PNG/SVG/PDF thumbnails).
 * Keeps rasterization consistent and excludes UI chrome that should not appear in files.
 *
 * Diagram nodes may show Markdown + KaTeX; KaTeX fonts load via global CSS. Export uses
 * waitForExportFonts() + document.fonts.ready so formulas rasterize reliably.
 */
/** Options shape shared by html-to-image export helpers (avoids static import). */
export interface HtmlToImageOptions {
  backgroundColor?: string | null
  pixelRatio?: number
  style?: Record<string, string>
  filter?: (node: Node) => boolean
  cacheBust?: boolean
  includeQueryParams?: boolean
}

export type DiagramCanvasCaptureOptions = Partial<HtmlToImageOptions>

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

function isVueFlowBackgroundNode(node: Node): boolean {
  return node instanceof HTMLElement && Boolean(node.closest('.vue-flow__background'))
}

export function getDiagramCanvasHtmlToImageOptions(
  overrides?: DiagramCanvasCaptureOptions
): HtmlToImageOptions {
  const { style: styleOverride, ...restOverrides } = overrides ?? {}
  return {
    backgroundColor: '#ffffff',
    pixelRatio: 2,
    style: {
      transform: 'none',
      ...styleOverride,
    },
    filter: (node: Node) => !isInsideVueFlowMinimap(node),
    ...restOverrides,
  }
}

/** PDF capture — transparent canvas, no dot grid, lower pixel ratio (see compressRasterDataUrlForA4Pdf). */
export function getDiagramCanvasPdfHtmlToImageOptions(
  overrides?: DiagramCanvasCaptureOptions
): HtmlToImageOptions {
  const { style: styleOverride, ...restOverrides } = overrides ?? {}
  return {
    backgroundColor: null,
    pixelRatio: 1,
    style: {
      transform: 'none',
      ...styleOverride,
    },
    filter: (node: Node) => !isInsideVueFlowMinimap(node) && !isVueFlowBackgroundNode(node),
    ...restOverrides,
  }
}
