const TILES_PER_PAGE = 9

export function buildWatermarkLayer(text: string): HTMLElement {
  const layer = document.createElement('div')
  layer.className = 'showcase-page-watermark'
  layer.setAttribute('aria-hidden', 'true')
  for (let i = 0; i < TILES_PER_PAGE; i += 1) {
    const span = document.createElement('span')
    span.textContent = text
    layer.appendChild(span)
  }
  return layer
}

export function stampWatermarkOnElement(pageEl: HTMLElement, text: string): void {
  if (!text.trim()) return
  if (pageEl.querySelector('.showcase-page-watermark')) return
  const layer = buildWatermarkLayer(text)
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
  root.querySelectorAll<HTMLElement>(pageSelector).forEach((page) => {
    stampWatermarkOnElement(page, text)
  })
}
