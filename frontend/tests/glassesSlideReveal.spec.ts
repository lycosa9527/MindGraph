import { afterEach, describe, expect, it, vi } from 'vitest'

import { builderDiagramSession } from '@/composables/training/builderDiagramBridge'
import { playGlassesReveal } from '@/composables/training/glassesSlideReveal'
import type { DiagramSession } from '@/stores/diagram'

function node(id: string, type: string, role?: string): HTMLElement {
  const element = document.createElement('div')
  element.className = 'vue-flow__node'
  element.dataset.id = id
  element.getBoundingClientRect = () =>
    ({
      left: 100,
      top: 80,
      width: 80,
      height: 80,
      right: 180,
      bottom: 160,
      x: 100,
      y: 80,
      toJSON() {
        return {}
      },
    }) as DOMRect
  const flow = document.querySelector('.vue-flow')
  flow?.appendChild(element)
  void type
  void role
  return element
}

afterEach(() => {
  builderDiagramSession.value = null
  document.body.replaceChildren()
  document.getElementById('glasses-reveal-lines-style')?.remove()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('double bubble preview', () => {
  it('hides the nodes, then enlarges the topics, and draws a line on the page', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    let frame: FrameRequestCallback | null = null
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      frame = callback
      return 1
    })
    vi.stubGlobal('cancelAnimationFrame', () => undefined)
    const stage = document.createElement('div')
    stage.className = 'builder-stage'
    const flow = document.createElement('div')
    flow.className = 'vue-flow'
    stage.appendChild(flow)
    document.body.appendChild(stage)
    const left = node('left-topic', 'topic')
    const shared = node('share', 'bubble', 'similarity')
    builderDiagramSession.value = {
      data: {
        nodes: [
          { id: 'left-topic', type: 'topic', text: '人工智能' },
          {
            id: 'share',
            type: 'bubble',
            text: '依赖算力',
            data: { doubleBubbleRole: 'similarity', groupIndex: 0 },
          },
        ],
        connections: [{ id: 'edge-left-share', source: 'left-topic', target: 'share' }],
      },
    } as unknown as DiagramSession

    const playing = playGlassesReveal(stage, 'stages', 160)
    await vi.advanceTimersByTimeAsync(0)
    expect(left.style.getPropertyValue('opacity')).toBe('0')
    expect(left.style.getPropertyPriority('scale')).toBe('important')
    expect(document.querySelector('[data-glasses-map-title]')?.textContent).toBe(
      'Double Bubble Map'
    )
    expect(document.querySelector('[data-glasses-stage-lines]')).toBeTruthy()

    await vi.advanceTimersByTimeAsync(40 + 980 + 280)
    expect(left.style.getPropertyValue('scale')).toBe('1.3')
    expect(shared.style.getPropertyValue('opacity')).toBe('0')

    await vi.advanceTimersByTimeAsync(520 + 240)
    expect(shared.style.getPropertyValue('scale')).toBe('1.12')
    frame?.(0)
    const svg = document.querySelector('[data-glasses-stage-lines]')
    expect(svg?.querySelector('path')?.getAttribute('d') || '').toContain('M ')

    await vi.runAllTimersAsync()
    await playing
    expect(document.querySelector('[data-glasses-map-title]')).toBeNull()
    expect(left.style.getPropertyValue('scale')).toBe('')
  })
})
