/**
 * Canvas export preferences + worksheet (打印学习单) modal lifecycle.
 * Persisted in sessionStorage; toolbar open/export stay event-bus driven.
 */
import { computed, ref, watch } from 'vue'

import { defineStore } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import {
  DEFAULT_CANVAS_EXPORT_OPTIONS,
  loadCanvasExportOptions,
  saveCanvasExportOptions,
  type CanvasExportColorMode,
  type CanvasExportOptions,
} from '@/config/canvasExportOptions'
import {
  DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
  loadCanvasWorksheetTextOptions,
  saveCanvasWorksheetTextOptions,
  type CanvasWorksheetTextOptions,
} from '@/config/canvasWorksheetText'
import { mergeCanvasExportOptions } from '@/utils/mergeCanvasExportOptions'

export const useCanvasExportStore = defineStore('canvasExport', () => {
  const exportOptions = ref<CanvasExportOptions>(loadCanvasExportOptions())
  const worksheetTextOptions = ref<CanvasWorksheetTextOptions>(
    loadCanvasWorksheetTextOptions()
  )
  const worksheetTextModalOpen = ref(false)
  const exportSessionActive = ref(false)
  /** Serializes preview capture + PDF export so viewport fit/restore cannot race. */
  let exportSessionChain: Promise<unknown> = Promise.resolve()

  /** Plain export payload — never injects worksheet headers. */
  const mergedExportOptions = computed(() =>
    mergeCanvasExportOptions(exportOptions.value)
  )

  /** 打印学习单 payload — includes persisted worksheet header/placement. */
  const worksheetExportOptions = computed(() =>
    mergeCanvasExportOptions(exportOptions.value, worksheetTextOptions.value)
  )

  watch(
    exportOptions,
    (value) => {
      saveCanvasExportOptions(value)
    },
    { deep: true }
  )

  watch(
    worksheetTextOptions,
    (value) => {
      saveCanvasWorksheetTextOptions(value)
    },
    { deep: true }
  )

  function setExportOptions(next: CanvasExportOptions): void {
    exportOptions.value = { ...next }
  }

  function patchExportOptions(patch: Partial<CanvasExportOptions>): void {
    exportOptions.value = { ...exportOptions.value, ...patch }
  }

  function resetExportOptions(): void {
    exportOptions.value = { ...DEFAULT_CANVAS_EXPORT_OPTIONS }
  }

  function setWorksheetTextOptions(next: CanvasWorksheetTextOptions): void {
    worksheetTextOptions.value = { ...next }
  }

  function resetWorksheetTextOptions(): void {
    worksheetTextOptions.value = { ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS }
  }

  function openWorksheetTextModal(): void {
    worksheetTextModalOpen.value = true
  }

  function closeWorksheetTextModal(): void {
    worksheetTextModalOpen.value = false
  }

  function setWorksheetTextModalOpen(open: boolean): void {
    worksheetTextModalOpen.value = open
  }

  function runExportSession<T>(fn: () => Promise<T>): Promise<T> {
    const result = exportSessionChain.then(async () => {
      exportSessionActive.value = true
      try {
        return await fn()
      } finally {
        exportSessionActive.value = false
      }
    })
    exportSessionChain = result.then(
      () => undefined,
      () => undefined
    )
    return result
  }

  function commitWorksheetAndExport(
    worksheetText: CanvasWorksheetTextOptions,
    colorMode: CanvasExportColorMode,
    format: 'pdf' | 'worksheet_docx' = 'pdf'
  ): void {
    setWorksheetTextOptions(worksheetText)
    patchExportOptions({ colorMode })
    closeWorksheetTextModal()
    eventBus.emit('toolbar:export_requested', {
      format,
      options: mergeCanvasExportOptions(
        { ...exportOptions.value, colorMode, worksheetText },
        worksheetText
      ),
    })
  }

  function hydrate(): void {
    exportOptions.value = loadCanvasExportOptions()
    worksheetTextOptions.value = loadCanvasWorksheetTextOptions()
  }

  return {
    exportOptions,
    worksheetTextOptions,
    worksheetTextModalOpen,
    exportSessionActive,
    mergedExportOptions,
    worksheetExportOptions,
    setExportOptions,
    patchExportOptions,
    resetExportOptions,
    setWorksheetTextOptions,
    resetWorksheetTextOptions,
    openWorksheetTextModal,
    closeWorksheetTextModal,
    setWorksheetTextModalOpen,
    runExportSession,
    commitWorksheetAndExport,
    hydrate,
  }
})
