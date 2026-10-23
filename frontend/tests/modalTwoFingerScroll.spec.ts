import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  classifyTwoFingerAxis,
  hasVerticalScrollRoom,
  installModalTwoFingerScroll,
  mergeScrollChains,
  pickVerticalScroller,
} from '@/utils/modalTwoFingerScroll'

type FingerPoint = { x: number; y: number; target: EventTarget }

function setScrollMetrics(
  el: HTMLElement,
  scrollHeight: number,
  clientHeight: number,
  scrollTop = 0
): void {
  Object.defineProperty(el, 'scrollHeight', { configurable: true, value: scrollHeight })
  Object.defineProperty(el, 'clientHeight', { configurable: true, value: clientHeight })
  el.scrollTop = scrollTop
}

function dispatchTouch(type: string, el: Element, points: FingerPoint[]): Event {
  const list = points.map((point) => ({
    clientX: point.x,
    clientY: point.y,
    target: point.target,
  }))
  const event = new Event(type, { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'touches', {
    configurable: true,
    value: {
      length: list.length,
      item: (index: number) => list[index] ?? null,
    },
  })
  el.dispatchEvent(event)
  return event
}

describe('modalTwoFingerScroll', () => {
  let uninstall: (() => void) | null = null

  beforeEach(() => {
    document.body.innerHTML = ''
    uninstall = installModalTwoFingerScroll()
  })

  afterEach(() => {
    uninstall?.()
    uninstall = null
    document.body.innerHTML = ''
  })

  it('locks a vertical two-finger move and keeps a horizontal one', () => {
    expect(classifyTwoFingerAxis(2, -3, 'undecided')).toBe('undecided')
    expect(classifyTwoFingerAxis(4, -30, 'undecided')).toBe('vertical')
    expect(classifyTwoFingerAxis(30, -4, 'undecided')).toBe('horizontal')
    expect(classifyTwoFingerAxis(40, 0, 'vertical')).toBe('vertical')
  })

  it('prefers the inner pane, then the dialog shell once that pane is at its end', () => {
    const inner = document.createElement('div')
    const outer = document.createElement('div')
    outer.append(inner)
    document.body.append(outer)
    setScrollMetrics(inner, 400, 100, 300)
    setScrollMetrics(outer, 900, 200, 0)
    expect(hasVerticalScrollRoom(inner, 10)).toBe(false)
    expect(pickVerticalScroller(mergeScrollChains([outer], [inner]), 10)).toBe(outer)
    setScrollMetrics(inner, 400, 100, 0)
    expect(pickVerticalScroller(mergeScrollChains([outer], [inner]), 10)).toBe(inner)
  })

  it('scrolls the dialog body when two fingers swipe up on a control', () => {
    document.body.innerHTML = `
      <div class="el-overlay-dialog">
        <div class="el-dialog">
          <div class="el-dialog__body" style="overflow-y: auto">
            <button type="button">显示</button>
          </div>
        </div>
      </div>
    `
    const body = document.querySelector<HTMLElement>('.el-dialog__body')
    const button = document.querySelector('button')
    if (!body || !button) throw new Error('fixture missing')
    setScrollMetrics(body, 900, 320, 0)

    dispatchTouch('touchstart', button, [
      { x: 40, y: 200, target: button },
      { x: 80, y: 210, target: button },
    ])
    dispatchTouch('touchmove', button, [
      { x: 42, y: 140, target: button },
      { x: 82, y: 150, target: button },
    ])

    expect(body.scrollTop).toBe(60)
  })

  it('scrolls an inner pane before the dialog body when two fingers swipe on a control', () => {
    document.body.innerHTML = `
      <div class="el-overlay-dialog" style="overflow-y: auto">
        <div class="el-dialog">
          <div class="el-dialog__body" style="overflow-y: auto">
            <div class="inner-pane" style="overflow-y: auto">
              <button type="button">显示</button>
            </div>
          </div>
        </div>
      </div>
    `
    const column = document.querySelector<HTMLElement>('.inner-pane')
    const body = document.querySelector<HTMLElement>('.el-dialog__body')
    const button = document.querySelector('button')
    if (!column || !body || !button) throw new Error('fixture missing')
    setScrollMetrics(column, 640, 180, 20)
    setScrollMetrics(body, 900, 400, 0)

    dispatchTouch('touchstart', button, [
      { x: 40, y: 200, target: button },
      { x: 80, y: 210, target: button },
    ])
    const move = dispatchTouch('touchmove', button, [
      { x: 42, y: 140, target: button },
      { x: 82, y: 150, target: button },
    ])

    expect(column.scrollTop).toBe(80)
    expect(body.scrollTop).toBe(0)
    expect(move.defaultPrevented).toBe(true)
  })

  it('continues on the dialog body when the inner pane is at the bottom, and leaves the overlay', () => {
    document.body.innerHTML = `
      <div class="el-overlay-dialog" style="overflow-y: auto">
        <div class="el-dialog">
          <div class="el-dialog__body" style="overflow-y: auto">
            <div class="inner-pane" style="overflow-y: auto">
              <button type="button">课题</button>
            </div>
          </div>
        </div>
      </div>
    `
    const overlay = document.querySelector<HTMLElement>('.el-overlay-dialog')
    const column = document.querySelector<HTMLElement>('.inner-pane')
    const body = document.querySelector<HTMLElement>('.el-dialog__body')
    const button = document.querySelector('button')
    if (!overlay || !column || !body || !button) throw new Error('fixture missing')
    setScrollMetrics(column, 400, 200, 200)
    setScrollMetrics(body, 900, 320, 10)
    setScrollMetrics(overlay, 1200, 500, 10)

    dispatchTouch('touchstart', button, [
      { x: 10, y: 180, target: button },
      { x: 50, y: 180, target: button },
    ])
    dispatchTouch('touchmove', button, [
      { x: 10, y: 120, target: button },
      { x: 50, y: 120, target: button },
    ])

    expect(column.scrollTop).toBe(200)
    expect(body.scrollTop).toBe(70)
    expect(overlay.scrollTop).toBe(10)
  })

  it('does not scroll a modal from one finger or from a two-finger swipe outside it', () => {
    document.body.innerHTML = `
      <div class="el-dialog"><div class="pane" style="overflow-y: auto"></div></div>
      <div id="canvas"></div>
    `
    const pane = document.querySelector<HTMLElement>('.pane')
    const canvas = document.querySelector<HTMLElement>('#canvas')
    if (!pane || !canvas) throw new Error('fixture missing')
    setScrollMetrics(pane, 500, 100, 0)

    dispatchTouch('touchstart', pane, [{ x: 10, y: 80, target: pane }])
    dispatchTouch('touchmove', pane, [{ x: 10, y: 20, target: pane }])
    expect(pane.scrollTop).toBe(0)

    dispatchTouch('touchstart', canvas, [
      { x: 0, y: 40, target: canvas },
      { x: 30, y: 40, target: canvas },
    ])
    const move = dispatchTouch('touchmove', canvas, [
      { x: 0, y: 0, target: canvas },
      { x: 30, y: 0, target: canvas },
    ])
    expect(pane.scrollTop).toBe(0)
    expect(move.defaultPrevented).toBe(false)
  })

  it('leaves a sideways two-finger drag alone and swallows the click after a scroll', () => {
    document.body.innerHTML = `
      <div class="swiss-glass-card">
        <div class="swiss-glass-card__body" style="overflow-y: auto">
          <button type="button">保存</button>
        </div>
      </div>
    `
    const body = document.querySelector<HTMLElement>('.swiss-glass-card__body')
    const button = document.querySelector('button')
    if (!body || !button) throw new Error('fixture missing')
    setScrollMetrics(body, 800, 200, 40)

    const fingers = [
      { x: 20, y: 100, target: button },
      { x: 70, y: 100, target: button },
    ]
    dispatchTouch('touchstart', button, fingers)
    const sideways = dispatchTouch('touchmove', button, [
      { x: 80, y: 102, target: button },
      { x: 130, y: 104, target: button },
    ])
    expect(body.scrollTop).toBe(40)
    expect(sideways.defaultPrevented).toBe(false)

    dispatchTouch('touchend', button, [])
    dispatchTouch('touchstart', button, fingers)
    dispatchTouch('touchmove', button, [
      { x: 20, y: 40, target: button },
      { x: 70, y: 40, target: button },
    ])
    expect(body.scrollTop).toBe(100)
    dispatchTouch('touchend', button, [])

    const ghostClick = new MouseEvent('click', { bubbles: true, cancelable: true })
    button.dispatchEvent(ghostClick)
    expect(ghostClick.defaultPrevented).toBe(true)

    dispatchTouch('touchstart', button, fingers)
    dispatchTouch('touchmove', button, [
      { x: 20, y: 10, target: button },
      { x: 70, y: 10, target: button },
    ])
    dispatchTouch('touchend', button, [])
    dispatchTouch('touchstart', button, [{ x: 24, y: 30, target: button }])
    const tap = new MouseEvent('click', { bubbles: true, cancelable: true })
    button.dispatchEvent(tap)
    expect(tap.defaultPrevented).toBe(false)
  })
})
