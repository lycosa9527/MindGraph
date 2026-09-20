import { findTsecCaptchaAnchor } from '@/utils/tsec/positionTsecCaptcha'

export const TSEC_EMBED_LAYER_CLASS = 'tsec-login-layer'
export const TSEC_EMBED_HOST_CLASS = 'tsec-login-layer__host'

const TSEC_EMBED_W_PX = 300
const TSEC_EMBED_H_PX = 230
const TSEC_VIEWPORT_PAD_PX = 12

export function placeTsecEmbedLayer(
  layer: HTMLElement,
  anchor: HTMLElement | null,
  viewport: Pick<Window, 'innerWidth' | 'innerHeight'> = window
): void {
  if (anchor) {
    const rect = anchor.getBoundingClientRect()
    const radius = window.getComputedStyle(anchor).borderRadius
    layer.style.left = `${rect.left}px`
    layer.style.top = `${rect.top}px`
    layer.style.width = `${rect.width}px`
    layer.style.height = `${rect.height}px`
    layer.style.borderRadius = radius
    return
  }
  const width = Math.min(TSEC_EMBED_W_PX, viewport.innerWidth - TSEC_VIEWPORT_PAD_PX * 2)
  const height = Math.min(TSEC_EMBED_H_PX, viewport.innerHeight - TSEC_VIEWPORT_PAD_PX * 2)
  layer.style.left = `${Math.max(TSEC_VIEWPORT_PAD_PX, (viewport.innerWidth - width) / 2)}px`
  layer.style.top = `${Math.max(TSEC_VIEWPORT_PAD_PX, (viewport.innerHeight - height) / 2)}px`
  layer.style.width = `${width}px`
  layer.style.height = `${height}px`
  layer.style.borderRadius = '1.35rem'
}

export function mountTsecCaptchaOnLoginCard(onCancel?: () => void): {
  host: HTMLElement
  release: () => void
} {
  const layer = document.createElement('div')
  layer.className = TSEC_EMBED_LAYER_CLASS
  layer.setAttribute('role', 'presentation')

  const host = document.createElement('div')
  host.className = TSEC_EMBED_HOST_CLASS
  layer.appendChild(host)
  document.body.appendChild(layer)

  const place = (): void => {
    placeTsecEmbedLayer(layer, findTsecCaptchaAnchor())
  }

  const onLayerClick = (event: MouseEvent): void => {
    if (event.target === layer) {
      onCancel?.()
    }
  }

  place()
  window.addEventListener('resize', place)
  window.addEventListener('scroll', place, true)
  layer.addEventListener('click', onLayerClick)

  return {
    host,
    release: () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
      layer.removeEventListener('click', onLayerClick)
      layer.remove()
    },
  }
}
