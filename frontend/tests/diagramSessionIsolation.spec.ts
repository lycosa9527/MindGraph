/**
 * Showcase preview sessions must not touch the editor Pinia diagram store.
 * Also covers new-canvas: leftover editor data must yield to loadDefaultTemplate.
 */
import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import {
  asDiagramSession,
  createDiagramSession,
  createDiagramViewBus,
  useDiagramStore,
} from '@/stores/diagram'

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

const pollutedCircleSpec = {
  topic: 'Xiaomi Car leftover from Showcase',
  context: ['A', 'B', 'C'],
}

describe('diagram session isolation (Showcase vs editor)', () => {
  beforeEach(() => {
    stubMatchMedia()
    setActivePinia(createPinia())
  })

  it('preview loadFromSpec does not change editor Pinia data or type', () => {
    const editor = useDiagramStore()
    expect(editor.loadDefaultTemplate('mindmap')).toBe(true)
    const editorType = editor.type
    const editorSnapshot = JSON.stringify(editor.data)

    const previewBus = createDiagramViewBus()
    const preview = asDiagramSession(
      createDiagramSession({
        mode: 'readonly',
        vueFlowId: 'showcase-preview-isolation',
        viewBus: previewBus,
        emitDiagramEvents: false,
      })
    )

    expect(preview.isReadonly).toBe(true)
    expect(editor.isReadonly).toBe(false)

    expect(
      preview.loadFromSpec(pollutedCircleSpec, 'circle_map', { emitLoaded: false })
    ).toBe(true)

    expect(preview.type).toBe('circle_map')
    expect(preview.data?.nodes?.some((n) => n.text.includes('Xiaomi'))).toBe(true)

    expect(editor.type).toBe(editorType)
    expect(JSON.stringify(editor.data)).toBe(editorSnapshot)
    expect(editor.isReadonly).toBe(false)

    preview.dispose()
  })

  it('preview viewBus zoom/fit does not emit on a separate editor viewBus', () => {
    const editorBus = createDiagramViewBus()
    const previewBus = createDiagramViewBus()

    const editorHits: string[] = []
    const previewHits: string[] = []
    editorBus.on('view:zoom_changed', () => {
      editorHits.push('zoom')
    })
    editorBus.on('view:fit_completed', () => {
      editorHits.push('fit')
    })
    previewBus.on('view:zoom_changed', () => {
      previewHits.push('zoom')
    })
    previewBus.on('view:fit_completed', () => {
      previewHits.push('fit')
    })

    const editor = asDiagramSession(
      createDiagramSession({
        mode: 'edit',
        vueFlowId: 'editor-dual',
        viewBus: editorBus,
        emitDiagramEvents: false,
      })
    )
    const preview = asDiagramSession(
      createDiagramSession({
        mode: 'readonly',
        vueFlowId: 'showcase-dual',
        viewBus: previewBus,
        emitDiagramEvents: false,
      })
    )

    preview.viewBus.emit('view:zoom_changed', { zoom: 1.5 })
    preview.viewBus.emit('view:fit_completed', { mode: 'full', animate: false })

    expect(previewHits).toEqual(['zoom', 'fit'])
    expect(editorHits).toEqual([])
    expect(editor.isReadonly).toBe(false)
    expect(preview.isReadonly).toBe(true)

    editor.dispose()
    preview.dispose()
  })

  it('new-canvas contract: leftover editor data is replaced by mindmap default template', () => {
    const editor = useDiagramStore()
    expect(editor.loadFromSpec(pollutedCircleSpec, 'circle_map')).toBe(true)
    expect(editor.type).toBe('circle_map')
    expect(editor.data?.nodes?.some((n) => n.text.includes('Xiaomi'))).toBe(true)

    // CanvasPage ?type=mindmap without diagramId always does this pair.
    expect(editor.loadDefaultTemplate('mindmap')).toBe(true)

    expect(editor.type).toBe('mindmap')
    expect(editor.data?.nodes?.some((n) => n.text.includes('Xiaomi'))).toBe(false)
  })

  it('quiet preview load does not emit diagram:loaded on the global app bus', () => {
    const hits: string[] = []
    const off = eventBus.on('diagram:loaded', () => {
      hits.push('loaded')
    })

    const preview = asDiagramSession(
      createDiagramSession({
        mode: 'readonly',
        vueFlowId: 'showcase-quiet-emit',
        viewBus: createDiagramViewBus(),
        emitDiagramEvents: false,
      })
    )
    expect(
      preview.loadFromSpec(pollutedCircleSpec, 'circle_map', { emitLoaded: true })
    ).toBe(true)

    expect(hits).toEqual([])
    off()
    preview.dispose()
  })
})
