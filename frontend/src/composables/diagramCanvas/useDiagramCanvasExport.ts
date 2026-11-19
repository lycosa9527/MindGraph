import { type Ref } from 'vue'

import { useDiagramExport, useDiagramSpecForSave, useLanguage } from '@/composables'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import type { CanvasExportOptions } from '@/config/canvasExportOptions'
import { ANIMATION } from '@/config/uiConfig'
import { useUIStore } from '@/stores'
import { runWithExportVisualMode } from '@/utils/canvasExportVisualMode'
import {
  prepareLearningSheetAnswersForFit,
  runLearningSheetRasterCapture,
} from '@/utils/diagramExportLearningSheet'
import { prepareDiagramCanvasForRasterCapture } from '@/utils/diagramExportPrep'
import { captureDiagramPngData } from '@/utils/diagramExportRasterCapture'
import { getDiagramCanvasPdfHtmlToImageOptions } from '@/utils/diagramHtmlToImage'
import { resolveDiagramTitleForSave } from '@/utils/diagramTitleForSave'
import { formatDoubleBubbleWorksheetTopic } from '@/utils/doubleBubbleWorksheetTopic'

type CanvasViewport = { x: number; y: number; zoom: number }

export interface UseDiagramCanvasExportOptions {
  vueFlowWrapper: Ref<HTMLElement | null>
  diagramStore: ReturnType<typeof useDiagramSession>
  fitForExport?: () => void | Promise<unknown>
  getViewport?: () => CanvasViewport
  setViewport?: (viewport: CanvasViewport, opts?: { duration?: number }) => void
}

export function useDiagramCanvasExport(options: UseDiagramCanvasExportOptions) {
  const { vueFlowWrapper, diagramStore, fitForExport, getViewport, setViewport } = options

  const { currentLanguage, t } = useLanguage()
  const uiStore = useUIStore()

  function getExportContainer(): HTMLElement | null {
    return vueFlowWrapper.value
  }

  function getExportTitle(): string {
    if (diagramStore.type === 'double_bubble_map' && !diagramStore.isUserEditedTitle) {
      const formatted = formatDoubleBubbleWorksheetTopic(diagramStore.data?.nodes, (left, right) =>
        t('canvas.worksheetText.doubleBubbleTopicDefault', { left, right })
      )
      if (formatted) return formatted
    }
    return resolveDiagramTitleForSave(
      diagramStore.effectiveTitle,
      diagramStore.type,
      currentLanguage.value
    )
  }

  const getExportSpec = useDiagramSpecForSave()

  const { exportByFormat, capturePngBlob, copyPngToClipboard } = useDiagramExport({
    getContainer: () => vueFlowWrapper.value,
    getDiagramSpec: getExportSpec,
    getTitle: getExportTitle,
  })

  /** Fit → rasterize diagram for worksheet modal preview → restore viewport. */
  async function captureWorksheetPreviewPng(
    exportOptions?: CanvasExportOptions
  ): Promise<string | null> {
    const container = vueFlowWrapper.value
    if (!container) return null

    const saved = getViewport?.() ?? null
    const restoreAnswers = await prepareLearningSheetAnswersForFit(diagramStore, exportOptions)
    try {
      await prepareDiagramCanvasForRasterCapture(fitForExport, {
        promptLanguage: uiStore.promptLanguage,
      })
      let dataUrl: string | null = null
      await runWithExportVisualMode(uiStore, container, exportOptions, async () => {
        const capture = await runLearningSheetRasterCapture(
          diagramStore,
          exportOptions,
          () =>
            captureDiagramPngData(
              container,
              getDiagramCanvasPdfHtmlToImageOptions({ pixelRatio: 1 })
            ),
          'below',
          container
        )
        dataUrl = capture.dataUrl
      })
      return dataUrl
    } finally {
      restoreAnswers()
      if (saved && setViewport) {
        setViewport(saved, { duration: ANIMATION.DURATION_FAST })
      }
    }
  }

  return {
    getExportContainer,
    getExportTitle,
    getExportSpec,
    exportByFormat,
    capturePngBlob,
    copyPngToClipboard,
    captureWorksheetPreviewPng,
  }
}
