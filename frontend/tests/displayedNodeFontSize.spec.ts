import { createApp, defineComponent, h, nextTick, ref } from 'vue'

import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCanvasToolbarFormatting } from '@/composables/canvasToolbar/useCanvasToolbarFormatting'
import { useDiagramStore } from '@/stores/diagram'
import { displayedNodeFontSize } from '@/utils/displayedNodeFontSize'

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

describe('displayedNodeFontSize', () => {
  it('keeps a stored topic size instead of the 18px role default', () => {
    expect(
      displayedNodeFontSize('circle_map', { id: 'topic', type: 'center' }, { fontSize: 20 }, [])
    ).toBe(20)
  })

  it('uses the role default when a thinking-map node has no size', () => {
    expect(displayedNodeFontSize('circle_map', { id: 'topic', type: 'center' }, {}, [])).toBe(18)
  })

  it('uses 16px for a mind-map branch that has no stored size', () => {
    expect(displayedNodeFontSize('mindmap', { id: 'branch-1', type: 'branch' }, {}, [])).toBe(16)
  })
})

describe('floating toolbar font size', () => {
  let app: ReturnType<typeof createApp> | null = null
  let readSize: (() => number) | null = null
  let pickSize: ((size: number) => void) | null = null
  const pinnedId = ref<string | null>(null)

  function mountFormatting(): void {
    const pinia = createPinia()
    setActivePinia(pinia)
    pinnedId.value = null
    const Probe = defineComponent({
      setup() {
        const formatting = useCanvasToolbarFormatting({
          silentUpdates: true,
          pinnedNodeId: pinnedId,
        })
        readSize = () => formatting.fontSize.value
        pickSize = (size: number) => formatting.handleFontSizePick(size)
        return () => h('div')
      },
    })
    app = createApp(Probe)
    app.use(pinia)
    app.mount(document.createElement('div'))
    const store = useDiagramStore()
    expect(store.loadDefaultTemplate('circle_map')).toBe(true)
  }

  beforeEach(() => {
    stubMatchMedia()
    readSize = null
    mountFormatting()
  })

  afterEach(() => {
    document.body.replaceChildren()
    app?.unmount()
    app = null
  })

  it('follows the selected node, including a custom topic size', async () => {
    const store = useDiagramStore()
    store.selectNodes('topic')
    await nextTick()
    expect(readSize?.()).toBe(18)

    store.updateNode('topic', { style: { fontSize: 20 } })
    await nextTick()
    expect(readSize?.()).toBe(20)

    const context = store.data?.nodes.find((node) => node.type === 'bubble')
    expect(context).toBeTruthy()
    store.selectNodes(context?.id ?? '')
    await nextTick()
    expect(readSize?.()).toBe(16)
  })

  it('uses the font size painted on the node when it differs from the stored default', async () => {
    const store = useDiagramStore()
    const node = document.createElement('div')
    node.className = 'vue-flow__node'
    node.dataset.id = 'topic'
    const shell = document.createElement('div')
    shell.className = 'circle-node'
    shell.style.fontSize = '22px'
    const label = document.createElement('span')
    label.className = 'inline-edit-plain'
    label.textContent = '算法'
    shell.appendChild(label)
    node.appendChild(shell)
    document.body.appendChild(node)

    pinnedId.value = 'topic'
    store.selectNodes('topic')
    await nextTick()
    await nextTick()
    expect(readSize?.()).toBe(22)
  })

  it('keeps a picked size when the node has not repainted yet', async () => {
    const store = useDiagramStore()
    const node = document.createElement('div')
    node.className = 'vue-flow__node'
    node.dataset.id = 'topic'
    const label = document.createElement('span')
    label.className = 'inline-edit-plain'
    label.style.fontSize = '18px'
    label.textContent = '算法'
    node.appendChild(label)
    document.body.appendChild(node)

    pinnedId.value = 'topic'
    store.selectNodes('topic')
    await nextTick()
    await nextTick()
    expect(readSize?.()).toBe(18)

    pickSize?.(20)
    await nextTick()
    await nextTick()
    await nextTick()
    expect(readSize?.()).toBe(20)
    expect(store.data?.nodes.find((item) => item.id === 'topic')?.style?.fontSize).toBe(20)
  })
})
