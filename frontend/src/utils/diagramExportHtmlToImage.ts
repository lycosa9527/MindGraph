/** Lazy singleton for html-to-image (PNG/SVG/PDF export). */
let htmlToImageModule: typeof import('html-to-image') | null = null

export async function loadHtmlToImageModule(): Promise<typeof import('html-to-image')> {
  if (!htmlToImageModule) {
    htmlToImageModule = await import('html-to-image')
  }
  return htmlToImageModule
}
