import { afterEach, describe, expect, it } from 'vitest'

import {
  CANVAS_CHROME_BOTTOM_FALLBACK_PX,
  measureCanvasChromeBottomPx,
} from '@/composables/canvas/useCanvasChromeBottomOffset'

function mountRect(tag: string, attrs: Record<string, string>, bottom: number, height: number) {
  const el = document.createElement(tag)
  for (const [key, value] of Object.entries(attrs)) {
    el.setAttribute(key, value)
  }
  Object.defineProperty(el, 'getBoundingClientRect', {
    value: () => ({
      x: 0,
      y: bottom - height,
      width: 800,
      height,
      top: bottom - height,
      right: 800,
      bottom,
      left: 0,
      toJSON: () => ({}),
    }),
  })
  document.body.appendChild(el)
  return el
}

describe('measureCanvasChromeBottomPx', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('falls back when no chrome is mounted', () => {
    expect(measureCanvasChromeBottomPx()).toBe(CANVAS_CHROME_BOTTOM_FALLBACK_PX)
  })

  it('prefers the live session banner over the toolbar', () => {
    mountRect('header', { class: 'canvas-chrome' }, 96, 96)
    mountRect('div', { 'data-collab-session-banner': '' }, 132, 36)
    expect(measureCanvasChromeBottomPx()).toBe(132)
  })

  it('uses ribbon chrome when the session banner is not present', () => {
    mountRect('div', { class: 'canvas-top-bar canvas-top-bar--mindmap' }, 88, 88)
    expect(measureCanvasChromeBottomPx()).toBe(88)
  })

  it('ignores a zero-height banner so the toolbar remains the anchor', () => {
    mountRect('header', { class: 'canvas-chrome' }, 48, 48)
    mountRect('div', { 'data-collab-session-banner': '' }, 48, 0)
    expect(measureCanvasChromeBottomPx()).toBe(48)
  })
})
