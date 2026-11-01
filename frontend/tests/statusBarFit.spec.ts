import { afterEach, describe, expect, it, vi } from 'vitest'

import { statusBarUsedWidth } from '@/utils/statusBarFit'

function widthBox(width: number): HTMLElement {
  const el = document.createElement('div')
  Object.defineProperty(el, 'clientWidth', { value: width })
  return el
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('statusBarUsedWidth', () => {
  it('counts cluster content and ignores empty space in a stretched center', () => {
    const bar = widthBox(800)
    const left = widthBox(120)
    const center = widthBox(480)
    const right = widthBox(160)
    const leftChild = document.createElement('span')
    const centerChild = document.createElement('span')
    const rightChild = document.createElement('span')
    Object.defineProperty(leftChild, 'offsetWidth', { value: 120 })
    Object.defineProperty(centerChild, 'offsetWidth', { value: 200 })
    Object.defineProperty(rightChild, 'offsetWidth', { value: 180 })
    const hidden = widthBox(0)
    left.append(leftChild)
    center.append(centerChild)
    right.append(rightChild)
    bar.append(left, hidden, center, right)
    vi.spyOn(window, 'getComputedStyle').mockImplementation((el: Element) => {
      if (el === bar) {
        return {
          paddingLeft: '16px',
          paddingRight: '16px',
          columnGap: '12px',
        } as CSSStyleDeclaration
      }
      return { columnGap: '0px' } as CSSStyleDeclaration
    })
    // Padding 32, two gaps, left 120, center content 200, right content 180.
    // The zero-width cluster is not laid out, so it does not add a third gap.
    expect(statusBarUsedWidth(bar)).toBe(556)
  })

  it('returns 0 before the bar has a width', () => {
    const bar = widthBox(0)
    expect(statusBarUsedWidth(bar)).toBe(0)
  })
})
