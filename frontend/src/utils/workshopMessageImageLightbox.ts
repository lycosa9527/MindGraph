/**
 * Zulip-style click-to-enlarge for 研习社 markdown images.
 *
 * Zulip binds clicks on `#main_div, #compose .preview_content` and opens
 * the lightbox instead of following the image link. Role-cat stickers stay
 * inline like emoji and are not enlarged.
 */

export const WORKSHOP_ROLE_ASSET_MARKER = '/api/training/assets/roles/'

const MG_DIAGRAM_ALT = /^mg:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export interface WorkshopImageLightboxTarget {
  src: string
  filename: string
}

export function workshopImageSrc(img: HTMLImageElement): string {
  return img.getAttribute('src') || img.currentSrc || img.src || ''
}

export function isWorkshopLightboxImage(img: HTMLImageElement): boolean {
  const src = workshopImageSrc(img)
  return src.length > 0 && !src.includes(WORKSHOP_ROLE_ASSET_MARKER)
}

export function filenameFromWorkshopImage(img: HTMLImageElement, fallback: string): string {
  const alt = img.alt.trim()
  if (alt && !MG_DIAGRAM_ALT.test(alt)) {
    return alt
  }
  const src = workshopImageSrc(img)
  try {
    const path = new URL(src, 'https://mindgraph.local').pathname
    const last = path.split('/').filter(Boolean).pop() ?? ''
    if (last && last !== 'download' && /\.[a-z0-9]+$/i.test(last)) {
      return decodeURIComponent(last)
    }
  } catch {
    /* keep fallback */
  }
  return fallback
}

export function workshopImageLightboxFromClick(
  event: Event,
  fallbackFilename: string
): WorkshopImageLightboxTarget | null {
  const target = event.target
  if (!(target instanceof HTMLImageElement)) {
    return null
  }
  if (!isWorkshopLightboxImage(target)) {
    return null
  }
  const src = workshopImageSrc(target)
  if (!src) {
    return null
  }
  event.preventDefault()
  event.stopPropagation()
  return {
    src,
    filename: filenameFromWorkshopImage(target, fallbackFilename),
  }
}
