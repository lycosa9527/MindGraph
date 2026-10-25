import { createApp, h, nextTick } from 'vue'

import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import CircleNode from '@/components/diagram/nodes/CircleNode.vue'
import { useDiagramStore } from '@/stores/diagram'
import type { DiagramNode } from '@/types'
import { isBubbleMapAttributeNode } from '@/utils/bubbleMapIdentity'
import { isCircleMapContextNode } from '@/utils/circleMapIdentity'

function nodeProps(node: DiagramNode, diagramType: string) {
  return {
    id: node.id,
    type: 'circle' as const,
    data: {
      ...(node.data as object),
      label: node.text ?? '',
      nodeType: 'bubble',
      diagramType,
      style: node.style,
      originalNode: node,
    },
    selected: false,
    connectable: false,
    position: { x: 0, y: 0 },
    dimensions: { width: 0, height: 0 },
    dragging: false,
    resizing: false,
    zIndex: 1,
    targetPosition: 'top' as const,
    sourcePosition: 'bottom' as const,
    dragHandle: undefined,
    events: {},
  }
}

async function renderCircle(node: DiagramNode, diagramType: string): Promise<HTMLElement> {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp({
    name: 'CircleNodeBlankHarness',
    render() {
      return h(CircleNode, nodeProps(node, diagramType))
    },
  })
  app.mount(host)
  await nextTick()
  const disk = host.querySelector('.circle-node')
  if (!(disk instanceof HTMLElement)) throw new Error('circle node did not render')
  const painted = disk.cloneNode(true) as HTMLElement
  painted.style.cssText = disk.style.cssText
  app.unmount()
  host.remove()
  return painted
}

describe('blanked circle and bubble disks', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0)
      return 1
    })
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe(): void {}
        unobserve(): void {}
        disconnect(): void {}
      }
    )
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  async function paintBlankedDisk(
    diagramType: 'circle_map' | 'bubble_map',
    pick: (node: DiagramNode) => boolean
  ): Promise<{ width: string; height: string; maxWidth: string; layoutSize: number }> {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate(diagramType)
    const node = diagramStore.data?.nodes?.find(
      (item) => pick(item) && String(item.text ?? '').trim().length > 0
    )
    if (!node) throw new Error('expected a disk')
    const layoutSize = node.style?.size
    if (typeof layoutSize !== 'number' || layoutSize <= 40) {
      throw new Error(`expected a layout diameter above the content floor, got ${layoutSize}`)
    }
    diagramStore.setNodeDimensions(node.id, 40, 40)
    diagramStore.setLearningSheetMode(true)
    expect(diagramStore.emptyNodeForLearningSheet(node.id)).toBe(true)
    const blanked = diagramStore.data?.nodes?.find((item) => item.id === node.id)
    if (!blanked) throw new Error('blanked node missing')
    const hold = (blanked.data as { learningSheetHoldWidth?: number }).learningSheetHoldWidth
    expect(hold).toBe(40)

    const disk = await renderCircle(blanked, diagramType)
    return {
      width: disk.style.width,
      height: disk.style.height,
      maxWidth: disk.style.maxWidth,
      layoutSize,
    }
  }

  it('paints a blanked circle-map disk at the layout diameter', async () => {
    const painted = await paintBlankedDisk('circle_map', isCircleMapContextNode)
    expect(painted.width).toBe(`${painted.layoutSize}px`)
    expect(painted.height).toBe(`${painted.layoutSize}px`)
    expect(painted.maxWidth).toBe('')
  })

  it('paints a blanked bubble-map disk at the layout diameter', async () => {
    const painted = await paintBlankedDisk('bubble_map', isBubbleMapAttributeNode)
    expect(painted.width).toBe(`${painted.layoutSize}px`)
    expect(painted.height).toBe(`${painted.layoutSize}px`)
    expect(painted.maxWidth).toBe('')
  })

  it('still locks a blanked underline to the measured box', async () => {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('circle_map')
    const node = diagramStore.data?.nodes?.find(
      (item) => isCircleMapContextNode(item) && String(item.text ?? '').trim().length > 0
    )
    if (!node) throw new Error('expected a context node')
    diagramStore.updateNode(node.id, {
      style: { ...node.style, nodeShape: 'underline' },
    })
    diagramStore.setNodeDimensions(node.id, 160, 36)
    diagramStore.setLearningSheetMode(true)
    expect(diagramStore.emptyNodeForLearningSheet(node.id)).toBe(true)
    const blanked = diagramStore.data?.nodes?.find((item) => item.id === node.id)
    if (!blanked) throw new Error('blanked node missing')

    const disk = await renderCircle(blanked, 'circle_map')
    expect(disk.style.width).toBe('160px')
    expect(disk.style.maxWidth).toBe('160px')
    expect(disk.style.height).toBe('36px')
  })
})
