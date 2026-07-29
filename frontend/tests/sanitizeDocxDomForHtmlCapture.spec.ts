import { describe, expect, it } from 'vitest'

import { sanitizeDocxDomForHtmlCapture } from '@/utils/captureTeachingDocThumbnail'

const SVG_NS = 'http://www.w3.org/2000/svg'

describe('sanitizeDocxDomForHtmlCapture', () => {
  it('rewrites empty-href SVG image containers to g and keeps foreignObject text', () => {
    const root = document.createElement('div')
    const svg = document.createElementNS(SVG_NS, 'svg')
    const image = document.createElementNS(SVG_NS, 'image')
    const fo = document.createElementNS(SVG_NS, 'foreignObject')
    const label = document.createElement('span')
    label.textContent = '环节一'
    fo.appendChild(label)
    image.appendChild(fo)
    svg.appendChild(image)
    root.appendChild(svg)

    sanitizeDocxDomForHtmlCapture(root)

    expect(root.querySelector('image')).toBeNull()
    expect(root.querySelector('g')).not.toBeNull()
    expect(root.textContent).toContain('环节一')
  })

  it('removes empty decorative SVG images and broken HTML img src', () => {
    const root = document.createElement('div')
    const svg = document.createElementNS(SVG_NS, 'svg')
    const emptyImage = document.createElementNS(SVG_NS, 'image')
    emptyImage.setAttribute('fill', '#E46C0A')
    svg.appendChild(emptyImage)
    root.appendChild(svg)

    const brokenImg = document.createElement('img')
    brokenImg.setAttribute('src', '')
    root.appendChild(brokenImg)

    const okImg = document.createElement('img')
    okImg.setAttribute('src', 'data:image/png;base64,aa')
    root.appendChild(okImg)

    sanitizeDocxDomForHtmlCapture(root)

    expect(root.querySelector('image')).toBeNull()
    expect(root.querySelectorAll('img')).toHaveLength(1)
    expect(root.querySelector('img')?.getAttribute('src')).toContain('data:image/png')
  })

  it('keeps SVG images that already have a usable href', () => {
    const root = document.createElement('div')
    const svg = document.createElementNS(SVG_NS, 'svg')
    const image = document.createElementNS(SVG_NS, 'image')
    image.setAttribute('href', 'data:image/png;base64,aa')
    svg.appendChild(image)
    root.appendChild(svg)

    sanitizeDocxDomForHtmlCapture(root)

    expect(root.querySelector('image')).not.toBeNull()
    expect(root.querySelector('image')?.getAttribute('href')).toContain('data:image/png')
  })
})
