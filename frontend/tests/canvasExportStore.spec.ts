import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { DEFAULT_CANVAS_EXPORT_OPTIONS } from '@/config/canvasExportOptions'
import { DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS } from '@/config/canvasWorksheetText'
import { useCanvasExportStore } from '@/stores/canvasExport'

describe('useCanvasExportStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
  })

  it('hydrates defaults and opens worksheet modal via action', () => {
    const store = useCanvasExportStore()
    expect(store.exportOptions).toEqual(DEFAULT_CANVAS_EXPORT_OPTIONS)
    expect(store.worksheetTextOptions.showTopic).toBe(true)
    expect(store.worksheetTextModalOpen).toBe(false)
    store.openWorksheetTextModal()
    expect(store.worksheetTextModalOpen).toBe(true)
  })

  it('keeps plain merged export options header-free', () => {
    const store = useCanvasExportStore()
    store.setWorksheetTextOptions({
      ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
      topicText: 'Unit test topic',
      diagramScale: 0.5,
    })
    expect(store.mergedExportOptions.worksheetText).toBeUndefined()
    expect(store.worksheetExportOptions.worksheetText?.topicText).toBe('Unit test topic')
    expect(store.worksheetExportOptions.worksheetText?.diagramScale).toBe(0.5)
  })

  it('serializes concurrent export sessions instead of dropping them', async () => {
    const store = useCanvasExportStore()
    const order: string[] = []
    let release!: () => void
    const blocker = new Promise<void>((resolve) => {
      release = resolve
    })

    const first = store.runExportSession(async () => {
      order.push('first-start')
      await blocker
      order.push('first-end')
      return 'ok'
    })
    const second = store.runExportSession(async () => {
      order.push('second')
      return 'queued'
    })

    release()
    await expect(first).resolves.toBe('ok')
    await expect(second).resolves.toBe('queued')
    expect(order).toEqual(['first-start', 'first-end', 'second'])
  })

  it('commits worksheet settings then emits pdf export on the event bus', () => {
    const store = useCanvasExportStore()
    const emitSpy = vi.spyOn(eventBus, 'emit')
    const worksheetText = {
      ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
      topicText: 'Print me',
      diagramOffsetX: 0.2,
    }

    store.commitWorksheetAndExport(worksheetText, 'wireframe', 'pdf')

    expect(store.worksheetTextOptions.topicText).toBe('Print me')
    expect(store.exportOptions.colorMode).toBe('wireframe')
    expect(store.worksheetTextModalOpen).toBe(false)
    expect(emitSpy).toHaveBeenCalledWith(
      'toolbar:export_requested',
      expect.objectContaining({
        format: 'pdf',
        options: expect.objectContaining({
          colorMode: 'wireframe',
          worksheetText: expect.objectContaining({ topicText: 'Print me' }),
        }),
      })
    )
    emitSpy.mockRestore()
  })

  it('emits worksheet_docx format for document export', () => {
    const store = useCanvasExportStore()
    const emitSpy = vi.spyOn(eventBus, 'emit')
    store.commitWorksheetAndExport(
      { ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS },
      'color',
      'worksheet_docx'
    )
    expect(emitSpy).toHaveBeenCalledWith(
      'toolbar:export_requested',
      expect.objectContaining({ format: 'worksheet_docx' })
    )
    emitSpy.mockRestore()
  })
})
