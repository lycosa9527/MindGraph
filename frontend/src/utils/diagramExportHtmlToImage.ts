/**
 * Lazy singleton for html-to-image (PNG/SVG/PDF export).
 * Keep package.json pinned at 1.11.11 — 1.11.12+ deep-clones SVG without
 * inlining computed styles, so Vue Flow curves export with black ghost strokes
 * (bubkoo/html-to-image#496, #506).
 */
let htmlToImageModule: typeof import('html-to-image') | null = null

export async function loadHtmlToImageModule(): Promise<typeof import('html-to-image')> {
  if (!htmlToImageModule) {
    htmlToImageModule = await import('html-to-image')
  }
  return htmlToImageModule
}
