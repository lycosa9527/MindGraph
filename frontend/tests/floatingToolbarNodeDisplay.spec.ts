import { createApp, defineComponent, h, nextTick, ref } from 'vue'

import { type Pinia, createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCanvasToolbarFormatting } from '@/composables/canvasToolbar/useCanvasToolbarFormatting'
import { MIND_MAP_RAINBOW_TOPIC_COLORS } from '@/config/mindMapVibrantThemes'
import { useDiagramStore } from '@/stores/diagram'
import type { DiagramType, NodeStyle } from '@/types'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import {
  resolveFloatingToolbarNodeDisplay,
  resolveFloatingToolbarNodeShape,
} from '@/utils/floatingToolbarNodeDisplay'
import { THINKING_MAP_LEAF_TEXT } from '@/utils/thinkingMapChrome'

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

const THINKING_MAP_TOPICS = [
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
] as const satisfies readonly DiagramType[]

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

function topicNode(type: 'topic' | 'center' = 'topic') {
  return { id: 'topic', type, text: '主题' }
}

describe('resolveFloatingToolbarNodeDisplay', () => {
  it.each(THINKING_MAP_TOPICS)(
    'matches the painted %s topic when the spec stores no style',
    (diagramType) => {
      const node = topicNode(diagramType === 'circle_map' ? 'center' : 'topic')
      const display = resolveFloatingToolbarNodeDisplay({
        diagramType,
        node,
        style: {},
      })
      expect(display.nodeShape).toBe('oval')
      expect(display.backgroundColor).toBe(MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor)
      expect(display.textColor).toBe(MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor)
      expect(display.borderColor).toBe(MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor)
      expect(display.fontWeight).toBe('bold')
      expect(display.fontFamily).toBe(DIAGRAM_NODE_FONT_STACK)
      expect(display.textAlign).toBe('center')
    }
  )

  it('reads a concept-map topic as the painted pill, not thinking-map chrome', () => {
    const display = resolveFloatingToolbarNodeDisplay({
      diagramType: 'concept_map',
      node: topicNode(),
      style: {},
    })
    expect(display).toMatchObject({
      nodeShape: 'oval',
      backgroundColor: '#e3f2fd',
      textColor: '#000000',
      borderColor: '#35506b',
      fontWeight: 'bold',
    })
  })

  it('reads tree and brace labels as structure text, not a white body', () => {
    const tree = resolveFloatingToolbarNodeDisplay({
      diagramType: 'tree_map',
      node: { id: 'dim', type: 'label', text: '维度' },
      style: {},
    })
    expect(tree).toMatchObject({
      nodeShape: null,
      backgroundColor: 'transparent',
      borderColor: 'transparent',
      textColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
      fontWeight: 'normal',
      fontStyle: 'italic',
    })
  })

  it('leaves a bare bridge pair without a body', () => {
    const display = resolveFloatingToolbarNodeDisplay({
      diagramType: 'bridge_map',
      node: {
        id: 'pair-a',
        type: 'branch',
        text: 'hot',
        data: { pairIndex: 0, position: 'left' },
      },
      style: {},
    })
    expect(display.nodeShape).toBeNull()
    expect(display.backgroundColor).toBe('transparent')
    expect(display.borderColor).toBe('transparent')
    expect(display.textColor).toBe(THINKING_MAP_LEAF_TEXT)
    expect(display.fontWeight).toBe('normal')
  })

  it('follows a hand-painted topic instead of the layout chrome', () => {
    const style: NodeStyle = {
      nodeShape: 'rectangle',
      backgroundColor: '#ff00aa',
      borderColor: '#111111',
      textColor: '#222222',
      fontWeight: 'normal',
      fontFamily: 'KaiTi',
      textAlign: 'left',
    }
    const display = resolveFloatingToolbarNodeDisplay({
      diagramType: 'tree_map',
      node: { ...topicNode(), style },
      style,
    })
    expect(display.nodeShape).toBe('rectangle')
    expect(display.backgroundColor).toBe('#ff00aa')
    expect(display.borderColor).toBe('#111111')
    expect(display.textColor).toBe('#222222')
    expect(display.fontWeight).toBe('normal')
    expect(display.fontFamily).toBe('KaiTi')
    expect(display.textAlign).toBe('left')
  })

  it('uses the stored shape before the layout default', () => {
    expect(
      resolveFloatingToolbarNodeShape('bubble_map', topicNode(), { nodeShape: 'underline' })
    ).toBe('underline')
    expect(resolveFloatingToolbarNodeShape('bubble_map', topicNode(), {})).toBe('oval')
  })
})

describe('floating toolbar mounts on the already-selected topic', () => {
  let app: ReturnType<typeof createApp> | null = null

  type ToolbarRead = {
    nodeShape: string | null
    backgroundColor: string
    textColor: string
    borderColor: string
    fontWeight: string
    fontFamily: string
  }

  let read: (() => ToolbarRead) | null = null
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
          textColor: formatting.textColor.value,
          borderColor: formatting.borderColor.value,
          fontWeight: formatting.fontWeight.value,
          fontFamily: formatting.fontFamily.value,
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

  it.each(THINKING_MAP_TOPICS)(
    'shows the painted %s topic after the toolbar mounts',
    async (diagramType) => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const store = useDiagramStore()
      expect(store.loadDefaultTemplate(diagramType)).toBe(true)
      const topic = store.data?.nodes.find(
        (node) => node.type === 'topic' || node.type === 'center'
      )
      expect(topic).toBeTruthy()
      store.selectNodes(topic?.id ?? '')
      pinnedId.value = topic?.id ?? null
      mountFormatting(pinia)
      await nextTick()
      expect(read?.()).toMatchObject({
        nodeShape: 'oval',
        backgroundColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
        textColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
        borderColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
        fontWeight: 'bold',
        fontFamily: DIAGRAM_NODE_FONT_STACK,
      })
    }
  )

  it('updates the swatches when the selected topic is restyled', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDiagramStore()
    expect(store.loadDefaultTemplate('circle_map')).toBe(true)
    store.selectNodes('topic')
    pinnedId.value = 'topic'
    mountFormatting(pinia)
    await nextTick()
    store.updateNode('topic', {
      style: {
        ...(store.data?.nodes.find((node) => node.id === 'topic')?.style || {}),
        nodeShape: 'rectangle',
        backgroundColor: '#22c55e',
        borderColor: '#166534',
        textColor: '#052e16',
        fontWeight: 'normal',
      },
    })
    await nextTick()
    expect(read?.()).toMatchObject({
      nodeShape: 'rectangle',
      backgroundColor: '#22c55e',
      borderColor: '#166534',
      textColor: '#052e16',
      fontWeight: 'normal',
    })
  })
})
