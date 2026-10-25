/**
 * Renders the real bridge and learning-sheet overlays and checks the painted
 * answer rows do not share a line.
 */
import { computed, createApp, h, ref } from 'vue'

import { createPinia, getActivePinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import BraceOverlay from '@/components/diagram/BraceOverlay.vue'
import BridgeOverlay from '@/components/diagram/BridgeOverlay.vue'
import LearningSheetOverlay from '@/components/diagram/LearningSheetOverlay.vue'
import TreeMapOverlay from '@/components/diagram/TreeMapOverlay.vue'
import { DiagramSessionKey } from '@/composables/diagram/useDiagramSession'
import { type DiagramSession, asDiagramSession, createDiagramSession } from '@/stores/diagram'
import { DIAGRAM_FOOTER_SEPARATOR_OFFSET_Y } from '@/utils/diagramFooterBand'

const harness = vi.hoisted(() => ({
  nodes: [] as Array<{
    id: string
    position: { x: number; y: number }
    dimensions: { width: number; height: number }
    data?: object
  }>,
}))

vi.mock('@vue-flow/core', () => ({
  useVueFlow: () => ({
    viewport: ref({ x: 0, y: 0, zoom: 1 }),
    getViewport: () => ({ x: 0, y: 0, zoom: 1 }),
    getNodes: computed(() => harness.nodes),
  }),
}))

const NODE_HEIGHT = 50

function stubMatchMedia(): void {
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
}

function syncFlow(session: DiagramSession): void {
  harness.nodes = (session.data?.nodes ?? []).map((node) => ({
    id: node.id,
    position: { x: node.position?.x ?? 0, y: node.position?.y ?? 0 },
    dimensions: { width: 120, height: NODE_HEIGHT },
    data: node.data,
  }))
}

function lowestBottom(): number {
  return Math.max(...harness.nodes.map((node) => node.position.y + node.dimensions.height))
}

function mountDiagram(session: DiagramSession): { host: HTMLElement; unmount: () => void } {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const pinia = getActivePinia()
  if (!pinia) throw new Error('missing pinia')
  const app = createApp({
    render() {
      return h('div', [
        h(BridgeOverlay),
        h(BraceOverlay),
        h(TreeMapOverlay),
        h(LearningSheetOverlay),
      ])
    },
  })
  app.use(pinia)
  app.provide(DiagramSessionKey, session)
  app.mount(host)
  return {
    host,
    unmount() {
      app.unmount()
      host.remove()
    },
  }
}

function openSession(): DiagramSession {
  return asDiagramSession(
    createDiagramSession({
      mode: 'readonly',
      vueFlowId: 'footer-clearance',
      emitDiagramEvents: false,
    })
  )
}

function blankNodes(session: DiagramSession, nodeType: string): void {
  session.setLearningSheetMode(true)
  for (const node of session.data?.nodes ?? []) {
    if (node.type !== nodeType) continue
    session.emptyNodeForLearningSheet(node.id)
  }
}

function attrY(el: Element | null): number {
  return Number(el?.getAttribute('y') ?? el?.getAttribute('y1') ?? NaN)
}

describe('learning sheet footer clearance', () => {
  beforeEach(() => {
    stubMatchMedia()
    setActivePinia(createPinia())
    harness.nodes = []
  })

  it('hides suggested analogies while a learning sheet is open', () => {
    const session = openSession()
    expect(
      session.loadFromSpec(
        {
          dimension: '功能',
          analogies: [
            { left: '事物A1', right: '事物B1' },
            { left: '事物A2', right: '事物B2' },
          ],
          alternative_dimensions: ['结构', '位置'],
        },
        'bridge_map',
        { emitLoaded: false }
      )
    ).toBe(true)
    blankNodes(session, 'branch')
    syncFlow(session)

    const view = mountDiagram(session)
    const sheetLine = view.host.querySelector('.learning-sheet-overlay line')

    expect(view.host.querySelector('.alternative-label')).toBeNull()
    expect(view.host.querySelector('.bridge-overlay line[stroke-dasharray]')).toBeNull()
    expect(view.host.textContent).not.toContain('结构')
    expect(view.host.querySelectorAll('.as-label').length).toBeGreaterThan(0)
    expect(attrY(sheetLine)).toBe(lowestBottom() + DIAGRAM_FOOTER_SEPARATOR_OFFSET_Y)
    expect(view.host.textContent).toContain('事物A1')
    expect(view.host.textContent).toContain('Answers')

    view.unmount()
    session.dispose()
  })

  it('keeps suggested analogies when the diagram is not a learning sheet', () => {
    const session = openSession()
    expect(
      session.loadFromSpec(
        {
          dimension: '功能',
          analogies: [
            { left: '事物A1', right: '事物B1' },
            { left: '事物A2', right: '事物B2' },
          ],
          alternative_dimensions: ['结构', '位置'],
        },
        'bridge_map',
        { emitLoaded: false }
      )
    ).toBe(true)
    syncFlow(session)

    const view = mountDiagram(session)
    expect(view.host.querySelector('.alternative-label')?.textContent).toContain('analogy')
    expect(view.host.querySelector('.bridge-overlay line[stroke-dasharray]')).not.toBeNull()
    expect(view.host.textContent).toContain('结构')
    expect(view.host.querySelector('.learning-sheet-overlay')).toBeNull()

    view.unmount()
    session.dispose()
  })

  it('hides the brace and tree recommendation lines with their suggestions', () => {
    const brace = openSession()
    expect(
      brace.loadFromSpec(
        {
          whole: '整体',
          parts: [{ name: '部分', subparts: [{ name: '子部分' }] }],
          alternative_dimensions: ['功能'],
        },
        'brace_map',
        { emitLoaded: false }
      )
    ).toBe(true)
    syncFlow(brace)
    const shown = mountDiagram(brace)
    expect(shown.host.querySelector('.brace-overlay line[stroke-dasharray]')).not.toBeNull()
    expect(shown.host.textContent).toContain('功能')
    shown.unmount()

    brace.setLearningSheetMode(true)
    const hidden = mountDiagram(brace)
    expect(hidden.host.querySelector('.brace-overlay line[stroke-dasharray]')).toBeNull()
    expect(hidden.host.textContent).not.toContain('功能')
    hidden.unmount()
    brace.dispose()

    const tree = openSession()
    expect(
      tree.loadFromSpec(
        {
          topic: '主题',
          children: [{ text: '类别', children: [{ text: '项目' }] }],
          alternative_dimensions: ['角度'],
        },
        'tree_map',
        { emitLoaded: false }
      )
    ).toBe(true)
    syncFlow(tree)
    const treeShown = mountDiagram(tree)
    expect(treeShown.host.querySelector('.tree-map-overlay line[stroke-dasharray]')).not.toBeNull()
    expect(treeShown.host.textContent).toContain('角度')
    treeShown.unmount()

    tree.setLearningSheetMode(true)
    const treeHidden = mountDiagram(tree)
    expect(treeHidden.host.querySelector('.tree-map-overlay')).toBeNull()
    expect(treeHidden.host.textContent).not.toContain('角度')
    treeHidden.unmount()
    tree.dispose()
  })

  it('keeps circle-map reference answers on the node bottom', () => {
    const session = openSession()
    expect(
      session.loadFromSpec({ topic: '主题', context: ['甲', '乙', '丙'] }, 'circle_map', {
        emitLoaded: false,
      })
    ).toBe(true)
    blankNodes(session, 'bubble')
    syncFlow(session)

    const view = mountDiagram(session)
    expect(view.host.querySelector('.bridge-overlay')).toBeNull()
    const sheetLine = view.host.querySelector('.learning-sheet-overlay line')
    expect(attrY(sheetLine)).toBe(lowestBottom() + DIAGRAM_FOOTER_SEPARATOR_OFFSET_Y)
    expect(view.host.textContent).toContain('Answers')

    view.unmount()
    session.dispose()
  })
})
