import { createApp, h, nextTick } from 'vue'

import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import BranchNodeDiagram from '@/components/diagram/nodes/BranchNodeDiagram.vue'
import FlowNode from '@/components/diagram/nodes/FlowNode.vue'
import FlowSubstepNode from '@/components/diagram/nodes/FlowSubstepNode.vue'
import LabelNode from '@/components/diagram/nodes/LabelNode.vue'
import TopicNodeDiagram from '@/components/diagram/nodes/TopicNodeDiagram.vue'
import { loadLocaleMessages } from '@/i18n'
import { useDiagramStore } from '@/stores/diagram'
import { useUIStore } from '@/stores/ui'
import type { DiagramNode, DiagramType } from '@/types'

vi.mock('@vue-flow/core', () => ({
  Handle: { name: 'Handle', template: '<span class="vf-handle" />' },
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
  useVueFlow: () => ({ updateNodeInternals: () => undefined }),
}))

function stubBrowser(): void {
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
}

const PAINT: Record<string, object> = {
  topic: TopicNodeDiagram,
  flow: FlowNode,
  flowSubstep: FlowSubstepNode,
  branch: BranchNodeDiagram,
  label: LabelNode,
}

async function paint(node: DiagramNode, diagramType: DiagramType): Promise<HTMLElement> {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const component = PAINT[node.type ?? '']
  if (!component) throw new Error(`no paint for ${node.type}`)
  const app = createApp({
    name: 'BilingualPaintHarness',
    render() {
      return h(component, {
        id: node.id,
        type: node.type,
        data: {
          ...(node.data as object),
          label: node.text ?? '',
          labelSecondary: node.textSecondary,
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
        events: {},
      })
    },
  })
  app.mount(host)
  await nextTick()
  const painted = host.cloneNode(true) as HTMLElement
  app.unmount()
  host.remove()
  return painted
}

describe('bilingual paint for flow, multi-flow, and bridge', () => {
  beforeEach(async () => {
    stubBrowser()
    setActivePinia(createPinia())
    await loadLocaleMessages('zh')
    await loadLocaleMessages('en')
    const ui = useUIStore()
    ui.language = 'zh'
    ui.bilingualUiEnabled = true
    ui.presenterUiLocale = 'en'
  })

  it.each(['flow_map', 'multi_flow_map', 'bridge_map'] as const)(
    'paints a second line on every %s node',
    async (diagramType) => {
      const store = useDiagramStore()
      expect(store.loadDefaultTemplate(diagramType)).toBe(true)
      const nodes = store.data?.nodes ?? []
      expect(nodes.length).toBeGreaterThan(0)
      const missing = nodes.filter((node) => !(node.textSecondary ?? '').trim())
      expect(missing.map((node) => `${node.type}:${node.text}`)).toEqual([])

      for (const node of nodes) {
        const host = await paint(node, diagramType)
        const gloss = host.querySelector('.bilingual-node-secondary')
        expect(gloss?.textContent?.trim(), `${diagramType} ${node.text}`).toBe(
          node.textSecondary?.trim()
        )
      }
    }
  )
})
