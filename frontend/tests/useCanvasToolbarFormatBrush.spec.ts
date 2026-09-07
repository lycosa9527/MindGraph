import { createApp, defineComponent, h, nextTick } from 'vue'

import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  formatBrushActive,
  formatBrushLocked,
  resetFormatBrushState,
  useCanvasToolbarFormatting,
} from '@/composables/canvasToolbar/useCanvasToolbarFormatting'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore } from '@/stores/diagram'

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

function threePaintNodes(): { sourceId: string; targetId: string; otherId: string } {
  const store = useDiagramStore()
  const topic = store.data?.nodes.find((node) => node.id === 'topic' || node.type === 'topic')
  const branches = store.data?.nodes.filter((node) => node.type === 'branch') ?? []
  if (!topic || branches.length < 2) {
    throw new Error('expected a topic and at least two mind-map branches')
  }
  return { sourceId: branches[0].id, targetId: branches[1].id, otherId: topic.id }
}

describe('useCanvasToolbarFormatting format brush', () => {
  let app: ReturnType<typeof createApp> | null = null
  let handleFormatBrush: ((options?: { lock?: boolean }) => void) | null = null

  function mountFormatting(): void {
    const pinia = createPinia()
    setActivePinia(pinia)
    const Probe = defineComponent({
      setup() {
        const formatting = useCanvasToolbarFormatting({ silentUpdates: true })
        handleFormatBrush = formatting.handleFormatBrush
        return () => h('div')
      },
    })
    app = createApp(Probe)
    app.use(pinia)
    app.mount(document.createElement('div'))
  }

  beforeEach(() => {
    stubMatchMedia()
    resetFormatBrushState()
    handleFormatBrush = null
    mountFormatting()
    const store = useDiagramStore()
    expect(store.loadDefaultTemplate('mindmap')).toBe(true)
  })

  afterEach(() => {
    app?.unmount()
    app = null
    resetFormatBrushState()
  })

  it('copies persisted node styles and paints the next selected node once', async () => {
    const store = useDiagramStore()
    const { sourceId, targetId } = threePaintNodes()
    store.updateNode(sourceId, {
      style: {
        backgroundColor: '#ff0000',
        textColor: '#ffffff',
        borderColor: '#990000',
      },
    })
    store.selectNodes(sourceId)

    handleFormatBrush?.()
    expect(formatBrushActive.value).toBe(true)
    expect(formatBrushLocked.value).toBe(false)

    store.selectNodes(targetId)
    await nextTick()

    expect(store.data?.nodes.find((node) => node.id === targetId)?.style?.backgroundColor).toBe(
      '#ff0000'
    )
    expect(formatBrushActive.value).toBe(false)
  })

  it('keeps applying to each new node after a lock, then cancels on pane click', async () => {
    const store = useDiagramStore()
    const { sourceId, targetId, otherId } = threePaintNodes()
    store.selectNodes(sourceId)

    handleFormatBrush?.({ lock: true })
    expect(formatBrushActive.value).toBe(true)
    expect(formatBrushLocked.value).toBe(true)

    store.selectNodes(targetId)
    await nextTick()
    expect(formatBrushActive.value).toBe(true)
    expect(formatBrushLocked.value).toBe(true)

    store.selectNodes(otherId)
    await nextTick()
    expect(formatBrushActive.value).toBe(true)

    eventBus.emit('canvas:pane_clicked', {})
    expect(formatBrushActive.value).toBe(false)
    expect(formatBrushLocked.value).toBe(false)
  })

  it('cancels an active one-shot brush on Escape', () => {
    const store = useDiagramStore()
    const { sourceId } = threePaintNodes()
    store.selectNodes(sourceId)

    handleFormatBrush?.()
    expect(formatBrushActive.value).toBe(true)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(formatBrushActive.value).toBe(false)
  })
})
