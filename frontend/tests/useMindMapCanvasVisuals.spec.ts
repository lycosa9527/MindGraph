/**
 * Showcase isolation: mind-map v2 visuals must key off the injected preview session
 * (type + session-owned canvas mode), not the editor Pinia store / viewer UI preference.
 */
import { createPinia, setActivePinia } from 'pinia'
import { createApp, defineComponent, h, nextTick } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { DiagramSessionKey } from '@/composables/diagram/useDiagramSession'
import { useMindMapCanvasVisuals } from '@/composables/mindMap/useMindMapCanvasVisuals'
import { useFeatureFlagsStore, useUIStore } from '@/stores'
import {
  asDiagramSession,
  createDiagramSession,
  createDiagramViewBus,
  useDiagramStore,
} from '@/stores/diagram'
import { readShowcaseMindMapCanvasMode } from '@/utils/mindMapCanvasMode'

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

async function captureVisuals(
  pinia: ReturnType<typeof createPinia>,
  session: ReturnType<typeof asDiagramSession>
): Promise<boolean> {
  let captured = false
  const Probe = defineComponent({
    setup() {
      const useV2 = useMindMapCanvasVisuals()
      captured = useV2.value
      return () => h('div')
    },
  })
  const app = createApp({
    setup() {
      return () => h(Probe)
    },
  })
  app.use(pinia)
  app.provide(DiagramSessionKey, session)
  app.mount(document.createElement('div'))
  await nextTick()
  app.unmount()
  return captured
}

describe('useMindMapCanvasVisuals (Showcase session)', () => {
  beforeEach(() => {
    stubMatchMedia()
    setActivePinia(createPinia())
    vi.spyOn(useFeatureFlagsStore(), 'getFeatureMindmapV2Canvas').mockReturnValue(true)
  })

  it('returns v2 for preview mindmap while editor store is a non-mindmap type', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.spyOn(useFeatureFlagsStore(), 'getFeatureMindmapV2Canvas').mockReturnValue(true)
    useUIStore().setMindMapCanvasMode('v2', { persist: false })

    const editor = useDiagramStore()
    expect(editor.loadDefaultTemplate('circle_map')).toBe(true)
    expect(editor.type).toBe('circle_map')

    const preview = asDiagramSession(
      createDiagramSession({
        mode: 'readonly',
        vueFlowId: 'showcase-visuals',
        viewBus: createDiagramViewBus(),
        emitDiagramEvents: false,
        mindMapCanvasMode: readShowcaseMindMapCanvasMode(),
      })
    )
    expect(preview.loadDefaultTemplate('mindmap')).toBe(true)
    expect(preview.type).toBe('mindmap')
    expect(preview.mindMapCanvasMode).toBe('v2')

    const captured = await captureVisuals(pinia, preview)
    expect(editor.type).toBe('circle_map')
    expect(captured).toBe(true)

    preview.dispose()
  })

  it('Classic UI preference does not force Showcase preview off New canvas', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.spyOn(useFeatureFlagsStore(), 'getFeatureMindmapV2Canvas').mockReturnValue(true)
    useUIStore().setMindMapCanvasMode('legacy', { persist: false })

    const editor = useDiagramStore()
    editor.reconcileMindMapCanvasMode('v2', 'legacy')
    expect(editor.mindMapCanvasMode).toBe('legacy')

    const preview = asDiagramSession(
      createDiagramSession({
        mode: 'readonly',
        vueFlowId: 'showcase-classic-ui',
        viewBus: createDiagramViewBus(),
        emitDiagramEvents: false,
        mindMapCanvasMode: readShowcaseMindMapCanvasMode(),
      })
    )
    expect(preview.mindMapCanvasMode).toBe('v2')
    expect(preview.loadDefaultTemplate('mindmap')).toBe(true)

    const captured = await captureVisuals(pinia, preview)
    expect(useUIStore().mindMapCanvasMode).toBe('legacy')
    expect(editor.mindMapCanvasMode).toBe('legacy')
    expect(captured).toBe(true)

    preview.dispose()
  })

  it('session hydrate uses session canvas mode, not UI store', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.spyOn(useFeatureFlagsStore(), 'getFeatureMindmapV2Canvas').mockReturnValue(true)
    useUIStore().setMindMapCanvasMode('legacy', { persist: false })

    const preview = asDiagramSession(
      createDiagramSession({
        mode: 'readonly',
        vueFlowId: 'showcase-hydrate',
        viewBus: createDiagramViewBus(),
        emitDiagramEvents: false,
        mindMapCanvasMode: 'v2',
      })
    )

    const dualBucketSpec = {
      topic: 'Showcase hydrate',
      leftBranches: [{ text: 'L1', children: [] }],
      rightBranches: [{ text: 'R1', children: [] }],
      _mindmap_canvas: {
        legacy: { theme: null },
        v2: { theme: 'ocean' },
      },
    }

    expect(preview.loadFromSpec(dualBucketSpec, 'mindmap', { emitLoaded: false })).toBe(true)
    expect(preview.mindMapCanvasMode).toBe('v2')
    expect(preview.data?._mindmap_theme).toBe('ocean')
    // Initial loader must also use session mode (v2 nodes get shape styles).
    const topic = preview.data?.nodes?.find((n) => n.id === 'topic')
    expect(topic?.style?.nodeShape).toBeTruthy()
    expect(useUIStore().mindMapCanvasMode).toBe('legacy')

    preview.dispose()
  })

  it('readShowcaseMindMapCanvasMode follows the v2 feature flag', () => {
    vi.spyOn(useFeatureFlagsStore(), 'getFeatureMindmapV2Canvas').mockReturnValue(true)
    expect(readShowcaseMindMapCanvasMode()).toBe('v2')
    vi.spyOn(useFeatureFlagsStore(), 'getFeatureMindmapV2Canvas').mockReturnValue(false)
    expect(readShowcaseMindMapCanvasMode()).toBe('legacy')
  })
})
