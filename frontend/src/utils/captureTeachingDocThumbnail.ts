/**
 * Helpers for teaching-design document DOM capture (cover sanitization).
 */
const SVG_NS = 'http://www.w3.org/2000/svg'
const XLINK_NS = 'http://www.w3.org/1999/xlink'

function readSvgImageHref(el: Element): string {
  // Avoid `instanceof SVGImageElement` — jsdom test env may not define it.
  const animated = (el as Element & { href?: { baseVal?: string } }).href
  if (animated && typeof animated === 'object') {
    const base = String(animated.baseVal ?? '').trim()
    if (base) return base
  }
  return (
    el.getAttribute('href')?.trim() ||
    el.getAttributeNS(XLINK_NS, 'href')?.trim() ||
    el.getAttribute('xlink:href')?.trim() ||
    ''
  )
}

/**
 * docx-preview draws Word shapes as SVG ``<image>`` nodes with empty href and
 * nested ``foreignObject`` text. html-to-image treats ``<image>`` as bitmaps and
 * rejects empty/broken hrefs (``Failed to parse URL from ?…``), aborting cover capture.
 */
export function sanitizeDocxDomForHtmlCapture(root: HTMLElement): void {
  root.querySelectorAll('image').forEach((el) => {
    const href = readSvgImageHref(el)
    if (href && !href.startsWith('?')) return
    if (el.childNodes.length > 0) {
      const group = document.createElementNS(SVG_NS, 'g')
      while (el.firstChild) {
        group.appendChild(el.firstChild)
      }
      el.replaceWith(group)
      return
    }
    el.remove()
  })

  root.querySelectorAll('img').forEach((img) => {
    const src = img.getAttribute('src')?.trim() || ''
    if (!src || src.startsWith('?')) {
      img.remove()
    }
  })
}
