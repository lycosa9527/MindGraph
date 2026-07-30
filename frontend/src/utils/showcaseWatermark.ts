/** Showcase document/diagram page watermark helpers. */

const WATERMARK_COLS = 3
const WATERMARK_ROW_PITCH_PX = 100
const WATERMARK_MIN_ROWS = 8

function tileCountForElement(pageEl: HTMLElement): number {
  const height = Math.max(pageEl.clientHeight, pageEl.scrollHeight, pageEl.offsetHeight, 640)
  const rows = Math.max(WATERMARK_MIN_ROWS, Math.ceil(height / WATERMARK_ROW_PITCH_PX) + 2)
  return WATERMARK_COLS * rows
}

export function buildWatermarkLayer(text: string, tileCount = WATERMARK_COLS * WATERMARK_MIN_ROWS): HTMLElement {
  const layer = document.createElement('div')
  layer.className = 'showcase-page-watermark'
  layer.setAttribute('aria-hidden', 'true')
  const count = Math.max(WATERMARK_COLS * WATERMARK_MIN_ROWS, tileCount)
  for (let i = 0; i < count; i += 1) {
    const span = document.createElement('span')
    span.textContent = text
    layer.appendChild(span)
  }
  return layer
}

export function stampWatermarkOnElement(pageEl: HTMLElement, text: string): void {
  if (!text.trim()) return
  if (pageEl.querySelector('.showcase-page-watermark')) return
  const layer = buildWatermarkLayer(text.trim(), tileCountForElement(pageEl))
  if (getComputedStyle(pageEl).position === 'static') {
    pageEl.classList.add('showcase-watermark-host')
  }
  pageEl.appendChild(layer)
}

export function stampWatermarksInContainer(
  root: HTMLElement,
  text: string,
  pageSelector: string
): void {
  if (!text.trim()) return
  const pages = root.querySelectorAll<HTMLElement>(pageSelector)
  if (pages.length === 0) {
    stampWatermarkOnElement(root, text)
    return
  }
  pages.forEach((page) => {
    stampWatermarkOnElement(page, text)
  })
}

/**
 * Re-stamp after layout so tall pages get enough tiles.
 * Call once after fonts/images settle (rAF is enough for docx-preview).
 */
export function refreshWatermarkDensity(root: HTMLElement, text: string): void {
  if (!text.trim()) return
  root.querySelectorAll<HTMLElement>('.showcase-page-watermark').forEach((layer) => {
    const host = layer.parentElement
    if (!host) return
    layer.remove()
    stampWatermarkOnElement(host, text.trim())
  })
}
