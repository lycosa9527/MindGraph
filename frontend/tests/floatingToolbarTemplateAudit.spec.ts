/**
 * Production sweep: every default-template node type vs the toolbar read.
 */
import { createApp, defineComponent, h, nextTick, ref } from 'vue'

import { type Pinia, createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCanvasToolbarFormatting } from '@/composables/canvasToolbar/useCanvasToolbarFormatting'
import { MIND_MAP_RAINBOW_TOPIC_COLORS } from '@/config/mindMapVibrantThemes'
import { useDiagramStore } from '@/stores/diagram'
import type { DiagramType } from '@/types'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import { resolveFloatingToolbarNodeDisplay } from '@/utils/floatingToolbarNodeDisplay'
import { thinkingMapRoleChrome } from '@/utils/thinkingMapChrome'
import { thinkingMapStructureColor } from '@/utils/thinkingMapConnectionStroke'
import { thinkingMapDisplayedNodeColors } from '@/utils/thinkingMapNodePaint'

vi.mock('@/composables/core/useLanguage', () => ({
  useLanguage: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('@/composables/core/useNotifications', () => ({
  useNotifications: () => ({
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    warningKey: vi.fn(),
    successKey: vi.fn(),
  }),
}))

const TEMPLATES: DiagramType[] = [
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
  'concept_map',
  'mindmap',
]

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

describe('floating toolbar template audit', () => {
  beforeEach(() => {
    stubMatchMedia()
    setActivePinia(createPinia())
  })

  it('reads chrome, structure, and concept paint for every default-template node', () => {
    const store = useDiagramStore()
    const seen = new Set<string>()

    for (const diagramType of TEMPLATES) {
      expect(store.loadDefaultTemplate(diagramType)).toBe(true)
      const nodes = store.data?.nodes ?? []
      const connections = store.data?.connections ?? []
      const themeId = store.data?._mindmap_theme
      expect(nodes.length).toBeGreaterThan(0)

      for (const node of nodes) {
        seen.add(`${diagramType}:${node.type}`)
        const style = { ...(store.getNodeStyle(node.id) || {}), ...(node.style || {}) }
        const chrome = thinkingMapRoleChrome(diagramType, node, connections)
        const paint = thinkingMapDisplayedNodeColors(diagramType, themeId, node, style, connections)
        const display = resolveFloatingToolbarNodeDisplay({
          diagramType,
          themeId,
          mindmapDiagramStyle: store.data?._mindmap_diagram_style,
          node,
          style,
          connections,
        })

        if (node.type === 'label') {
          const bridge = Boolean(node.data?.isDimensionLabel)
          expect(display.nodeShape, `${diagramType} label shape`).toBeNull()
          expect(display.backgroundColor).toBe('transparent')
          expect(display.borderColor).toBe('transparent')
          expect(display.textColor).toBe(thinkingMapStructureColor(themeId))
          expect(display.fontWeight).toBe(bridge ? 'bold' : 'normal')
          expect(display.fontStyle).toBe(bridge ? 'normal' : 'italic')
          expect(display.textAlign).toBe(bridge ? 'right' : 'center')
          continue
        }

        if (node.type === 'boundary') {
          expect(display.nodeShape).toBeNull()
          expect(display.backgroundColor).toBe('transparent')
          expect(display.textColor).toBe('transparent')
          expect(display.borderColor).toBe(thinkingMapStructureColor(themeId))
          continue
        }

        if (diagramType === 'bridge_map') {
          expect(display.nodeShape).toBeNull()
          expect(display.backgroundColor).toBe('transparent')
          expect(display.borderColor).toBe('transparent')
          expect(display.fontWeight).toBe('normal')
          continue
        }

        if (diagramType === 'concept_map') {
          expect(display).toMatchObject({
            nodeShape: 'oval',
            backgroundColor: '#e3f2fd',
            textColor: '#000000',
            borderColor: '#35506b',
            fontWeight: 'bold',
            fontFamily: DIAGRAM_NODE_FONT_STACK,
          })
          continue
        }

        if (chrome || paint) {
          if (paint?.backgroundColor) expect(display.backgroundColor).toBe(paint.backgroundColor)
          else if (chrome?.backgroundColor) {
            expect(display.backgroundColor).toBe(chrome.backgroundColor)
          }
          if (paint?.textColor) expect(display.textColor).toBe(paint.textColor)
          else if (chrome?.textColor) expect(display.textColor).toBe(chrome.textColor)
          if (paint?.borderColor) expect(display.borderColor).toBe(paint.borderColor)
          else if (chrome?.borderColor) expect(display.borderColor).toBe(chrome.borderColor)
          expect(display.fontWeight).toBe(style.fontWeight || chrome?.fontWeight || 'normal')
          continue
        }

        if (style.backgroundColor) expect(display.backgroundColor).toBe(style.backgroundColor)
        if (style.borderColor) expect(display.borderColor).toBe(style.borderColor)
        if (style.textColor) expect(display.textColor).toBe(style.textColor)
      }
    }

    expect([...seen].sort()).toEqual([
      'brace_map:brace',
      'brace_map:label',
      'brace_map:topic',
      'bridge_map:branch',
      'bridge_map:label',
      'bubble_map:bubble',
      'bubble_map:topic',
      'circle_map:boundary',
      'circle_map:bubble',
      'circle_map:center',
      'concept_map:topic',
      'double_bubble_map:bubble',
      'double_bubble_map:topic',
      'flow_map:flow',
      'flow_map:flowSubstep',
      'flow_map:topic',
      'mindmap:branch',
      'mindmap:topic',
      'multi_flow_map:flow',
      'multi_flow_map:topic',
      'tree_map:branch',
      'tree_map:label',
      'tree_map:topic',
    ])
  })
})

describe('floating toolbar mounts after selection on every template type', () => {
  let app: ReturnType<typeof createApp> | null = null
  let read: (() => { nodeShape: string | null; backgroundColor: string }) | null = null
  const pinnedId = ref<string | null>(null)

  function mountFormatting(pinia: Pinia): void {
    const Probe = defineComponent({
      setup() {
        const formatting = useCanvasToolbarFormatting({
          silentUpdates: true,
          pinnedNodeId: pinnedId,
        })
        read = () => ({
          nodeShape: formatting.nodeShape.value,
          backgroundColor: formatting.backgroundColor.value,
        })
        return () => h('div')
      },
    })
    app = createApp(Probe)
    app.use(pinia)
    app.mount(document.createElement('div'))
  }

  beforeEach(() => {
    stubMatchMedia()
    read = null
    pinnedId.value = null
  })

  afterEach(() => {
    document.body.replaceChildren()
    app?.unmount()
    app = null
  })

  it.each([
    ['circle_map', 'center', 'oval', MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor],
    ['bubble_map', 'topic', 'oval', MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor],
    ['double_bubble_map', 'topic', 'oval', MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor],
    ['tree_map', 'topic', 'oval', MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor],
    ['brace_map', 'topic', 'oval', MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor],
    ['flow_map', 'topic', 'oval', MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor],
    ['multi_flow_map', 'topic', 'oval', MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor],
    ['bridge_map', 'branch', null, 'transparent'],
    ['concept_map', 'topic', 'oval', '#e3f2fd'],
  ] as const)(
    'mounts on a %s %s with the painted fill',
    async (diagramType, nodeType, shape, fill) => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const store = useDiagramStore()
      expect(store.loadDefaultTemplate(diagramType)).toBe(true)
      const node = store.data?.nodes.find((item) => item.type === nodeType)
      expect(node).toBeTruthy()
      store.selectNodes(node?.id ?? '')
      pinnedId.value = node?.id ?? null
      mountFormatting(pinia)
      await nextTick()
      expect(read?.()).toEqual({ nodeShape: shape, backgroundColor: fill })
    }
  )
})
