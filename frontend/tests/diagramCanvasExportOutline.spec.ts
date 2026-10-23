import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { beforeAll, describe, expect, it } from 'vitest'

const cssPath = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../src/components/diagram/diagramCanvasExportOutline.css'
)

beforeAll(() => {
  const style = document.createElement('style')
  style.textContent = readFileSync(cssPath, 'utf8')
  document.head.appendChild(style)
})

function mountCanvas(wireframe: boolean, mindMap = false): HTMLElement {
  const canvas = document.createElement('div')
  canvas.className = mindMap ? 'diagram-canvas mind-map-canvas' : 'diagram-canvas'
  const wrapper = document.createElement('div')
  wrapper.className = wireframe
    ? 'vue-flow-wrapper export-outline-wireframe'
    : 'vue-flow-wrapper'
  canvas.appendChild(wrapper)
  document.body.appendChild(canvas)
  return wrapper
}

function paintNode(wrapper: HTMLElement, className: string): HTMLElement {
  const node = document.createElement('div')
  node.className = className
  node.style.backgroundColor = '#4dabf7'
  node.style.color = '#ffffff'
  node.style.borderColor = '#1c7ed6'
  wrapper.appendChild(node)
  return node
}

describe('diagramCanvasExportOutline', () => {
  it('paints thinking-map nodes black on white during wireframe export', () => {
    const wrapper = mountCanvas(true)
    const node = paintNode(wrapper, 'circle-node')
    const style = getComputedStyle(node)
    expect(style.backgroundColor).toBe('rgb(255, 255, 255)')
    expect(style.color).toBe('rgb(17, 24, 39)')
    expect(style.borderTopColor).toBe('rgb(17, 24, 39)')
    expect(style.boxShadow).toBe('none')
    wrapper.parentElement?.remove()
  })

  it('keeps underline shapes as a rule instead of a filled box', () => {
    const wrapper = mountCanvas(true)
    const node = paintNode(wrapper, 'circle-node circle-node--underline')
    const rule = document.createElement('span')
    rule.className = 'node-shape-underline'
    rule.style.backgroundColor = '#4dabf7'
    node.appendChild(rule)
    expect(getComputedStyle(node).backgroundColor).toBe('rgba(0, 0, 0, 0)')
    expect(getComputedStyle(node).borderTopColor).toBe('rgba(0, 0, 0, 0)')
    expect(getComputedStyle(rule).backgroundColor).toBe('rgb(17, 24, 39)')
    wrapper.parentElement?.remove()
  })

  it('recolors dimension labels without painting a chip', () => {
    const wrapper = mountCanvas(true)
    const node = paintNode(wrapper, 'label-node')
    const style = getComputedStyle(node)
    expect(style.color).toBe('rgb(17, 24, 39)')
    expect(style.backgroundColor).toBe('rgba(0, 0, 0, 0)')
    wrapper.parentElement?.remove()
  })

  it('inks the circle-map boundary ring', () => {
    const wrapper = mountCanvas(true)
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.setAttribute('class', 'boundary-svg')
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
    circle.setAttribute('stroke', '#4dabf7')
    svg.appendChild(circle)
    wrapper.appendChild(svg)
    expect(getComputedStyle(circle).stroke).toBe('rgb(17, 24, 39)')
    wrapper.parentElement?.remove()
  })

  it('leaves theme colors in place for a color export', () => {
    const wrapper = mountCanvas(false)
    const node = paintNode(wrapper, 'circle-node')
    const style = getComputedStyle(node)
    expect(style.backgroundColor).toBe('rgb(77, 171, 247)')
    expect(style.color).toBe('rgb(255, 255, 255)')
    wrapper.parentElement?.remove()
  })

  it('does not restyle mind map v2 nodes', () => {
    const wrapper = mountCanvas(true, true)
    const node = paintNode(wrapper, 'topic-node')
    expect(getComputedStyle(node).backgroundColor).toBe('rgb(77, 171, 247)')
    wrapper.parentElement?.remove()
  })
})
